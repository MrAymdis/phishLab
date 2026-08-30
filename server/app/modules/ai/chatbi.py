"""ChatBI 自然语言问数（红线 5：禁止直接执行未经校验的 SQL）。

安全管线：意图 → SQL 模板 → sqlglot 结构化校验（仅 SELECT / 表白名单 /
禁 INTO / 强制 LIMIT）→ 数据权限注入（与 apply_data_scope 同口径改写）→
只读连接执行（独立只读账号优先，未配置时主库只读事务兜底）→ 审计留痕。

当前意图先由本地规则引擎命中（毫秒级、结果确定），未命中的长尾问法由 LLM 生成，
走同一管线；所有结果查询只读，不产生任何写操作。
"""
import logging
import re
from datetime import datetime, timedelta

import sqlglot
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlglot import exp

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.errors import BizError, ErrorCode
from app.db.session import engine

logger = logging.getLogger("phishlab.chatbi")

# 表白名单：ChatBI 可查询的表（LLM/规则生成的 SQL 只能引用这些表）
_CHATBI_TABLES = {
    "campaign": "演练活动",
    "campaign_target": "演练目标明细（投递/打开/点击/中招/举报）",
    "campaign_stat": "演练冗余统计",
    "track_event": "追踪事件（打开/点击/提交/附件运行/退信）",
    "emp_user": "员工档案",
    "emp_dept": "部门",
    "emp_risk_profile": "员工风险画像",
    "stat_daily": "日报归档",
    "training_assignment": "培训任务",
    "course": "课程",
    "mail_report": "邮件举报",
}

# 员工数据表：注入部门权限时的联表/子查询依据
_EMP_TABLES = {"emp_user", "emp_risk_profile"}
_USER_LINKED_TABLES = {"campaign_target", "track_event"}

_MAX_ROWS = 200  # 单次查询结果上限（未指定 LIMIT 时补 100，超出封顶 200）
_DEFAULT_LIMIT = 100

_SENT_STATUS = "('sent', 'delivered', 'bounced', 'failed')"

# ---------- 规则引擎：意图 → SQL 模板 ----------


def _parse_window(question: str) -> datetime:
    """从问题提取时间窗起点（近N天/本月/上月），默认近 30 天。"""
    now = datetime.now()
    m = re.search(r"近\s*(\d+)\s*天", question)
    if m:
        return now - timedelta(days=int(m.group(1)))
    if "本月" in question:
        return now.replace(day=1)
    if "上月" in question:
        first = now.replace(day=1)
        return (first - timedelta(days=1)).replace(day=1)
    return now - timedelta(days=30)


_TEMPLATES: list[tuple[re.Pattern, str, str]] = [
    # (正则, 标题, SQL 模板；:since 为时间窗参数，权限由注入层追加)
    # 举报类先匹配（"举报…部门"与部门正则存在重叠，优先级高的在前）
    (re.compile(r"举报.*(部门|排行|统计)"),
     "举报最多的部门",
     """SELECT COALESCE(d.name, '未知部门') AS dept, COUNT(m.id) AS reports
       FROM mail_report m
       LEFT JOIN emp_user u ON u.id = m.reporter_user_id
       LEFT JOIN emp_dept d ON d.id = u.dept_id
      WHERE m.created_at >= :since
      GROUP BY COALESCE(d.name, '未知部门')
      ORDER BY reports DESC"""),
    (re.compile(r"举报.*(趋势|走势|每日|每天)|趋势.*举报"),
     "举报趋势（按天）",
     """SELECT DATE(m.created_at) AS day, COUNT(m.id) AS reports
       FROM mail_report m
       LEFT JOIN emp_user u ON u.id = m.reporter_user_id
      WHERE m.created_at >= :since
      GROUP BY DATE(m.created_at)
      ORDER BY day"""),
    (re.compile(r"部门.*(中招|对比)|(?<!全)部(?=中招)|中招.*部门"),
     "部门中招对比",
     """SELECT d.name AS dept,
            COUNT(t.id) AS sent,
            SUM(CASE WHEN t.submit_flag = 1 OR t.attach_run_count > 0 THEN 1 ELSE 0 END) AS victim
       FROM campaign_target t
       JOIN emp_user u ON u.id = t.user_id
       JOIN emp_dept d ON d.id = u.dept_id
      WHERE t.send_status IN {sent_status}
        AND t.sent_at >= :since
      GROUP BY d.name
      ORDER BY victim DESC""".replace("{sent_status}", _SENT_STATUS)),
    (re.compile(r"中招.*(趋势|走势)|趋势.*中招"),
     "中招率趋势（按天）",
     """SELECT DATE(t.sent_at) AS day,
            COUNT(t.id) AS sent,
            SUM(CASE WHEN t.submit_flag = 1 OR t.attach_run_count > 0 THEN 1 ELSE 0 END) AS victim
       FROM campaign_target t
      WHERE t.send_status IN {sent_status}
        AND t.sent_at >= :since
      GROUP BY DATE(t.sent_at)
      ORDER BY day""".replace("{sent_status}", _SENT_STATUS)),
    (re.compile(r"(谁|员工).*(中招|最多)|中招.*(排行|最多)"),
     "中招次数最多的员工 TOP10",
     """SELECT u.name AS name, d.name AS dept, COUNT(*) AS victim_count
       FROM campaign_target t
       JOIN emp_user u ON u.id = t.user_id
       LEFT JOIN emp_dept d ON d.id = u.dept_id
      WHERE (t.submit_flag = 1 OR t.attach_run_count > 0)
        AND t.sent_at >= :since
      GROUP BY u.id, u.name, d.name
      ORDER BY victim_count DESC
      LIMIT 10"""),
    (re.compile(r"(高危|高风险).*(人员|员工|top|名单)|风险.*(最高|名单)"),
     "高危人员（风险等级 3）",
     """SELECT u.name AS name, d.name AS dept,
            p.total_score AS score, p.risk_level AS risk
       FROM emp_risk_profile p
       JOIN emp_user u ON u.id = p.user_id
       LEFT JOIN emp_dept d ON d.id = u.dept_id
      WHERE p.risk_level >= 3
      ORDER BY p.total_score DESC
      LIMIT 20"""),
    (re.compile(r"演练.*(中招|打开|点击|统计)|各场.*演练"),
     "各演练核心指标",
     """SELECT c.id AS id, c.name AS name, c.status AS status,
            COUNT(t.id) AS sent,
            SUM(CASE WHEN t.first_open_at IS NOT NULL THEN 1 ELSE 0 END) AS opened,
            SUM(CASE WHEN t.submit_flag = 1 OR t.attach_run_count > 0 THEN 1 ELSE 0 END) AS victim
       FROM campaign c
       LEFT JOIN campaign_target t ON t.campaign_id = c.id
      GROUP BY c.id, c.name, c.status
      ORDER BY c.id DESC
      LIMIT 20"""),
    (re.compile(r"培训.*(通过率|完成率|部门|统计)|(通过率|完成率).*部门"),
     "培训通过率最低的部门",
     """SELECT d.name AS dept,
            COUNT(a.id) AS assigned,
            SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) AS completed,
            ROUND(SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END)
                  / NULLIF(COUNT(a.id), 0) * 100, 1) AS pass_rate
       FROM training_assignment a
       JOIN emp_user u ON u.id = a.user_id
       LEFT JOIN emp_dept d ON d.id = u.dept_id
      GROUP BY d.name
      ORDER BY pass_rate
      LIMIT 20"""),
]


def _match_template(question: str) -> tuple[str, str] | None:
    for pattern, title, sql in _TEMPLATES:
        if pattern.search(question):
            return title, sql
    return None


# ---------- sqlglot 结构化校验 ----------


def _validate_sql(sql: str) -> str:
    """校验并规范化 SQL：必须单条 SELECT、表 ∈ 白名单、禁 INTO、强制 LIMIT。

    返回规范化后的 SQL；任何不合法输入直接抛 BizError（fail-closed）。
    """
    try:
        exprs = [e for e in sqlglot.parse(sql, read="mysql") if e is not None]
    except Exception as exc:
        raise BizError(ErrorCode.PARAM_INVALID, f"SQL 解析失败，拒绝执行：{exc}") from exc
    if len(exprs) != 1 or not isinstance(exprs[0], exp.Select):
        raise BizError(ErrorCode.PARAM_INVALID, "仅支持单条 SELECT 查询")
    sel = exprs[0]

    # 表白名单：扫描语句内所有表（含 JOIN/子查询），逐一校验
    for table in sel.find_all(sqlglot.exp.Table):
        name = table.name.lower()
        if name not in _CHATBI_TABLES:
            raise BizError(ErrorCode.PARAM_INVALID,
                           f"表 {name} 不在 ChatBI 表白名单内，拒绝执行")
    if sel.args.get("into"):
        raise BizError(ErrorCode.PARAM_INVALID, "禁止 INTO 写入语句")

    # 强制 LIMIT：未指定补默认值，超出封顶
    limit = sel.args.get("limit")
    if limit is None:
        sel = sel.limit(_DEFAULT_LIMIT)
    else:
        try:
            n = int(str(limit.expression.this))
            if n > _MAX_ROWS:
                sel = sel.limit(_MAX_ROWS)
        except (AttributeError, TypeError, ValueError):
            raise BizError(ErrorCode.PARAM_INVALID, "LIMIT 必须为数字")
    return sel.sql(dialect="mysql")


# ---------- 数据权限注入（与 apply_data_scope 同口径） ----------


def _scope_of(db: Session, account) -> dict | None:
    """计算账号数据范围：{"dept_ids": set[int], "self_only": bool}。

    返回 None = 全量可见（无角色或超管/全量角色）；口径与 core.deps.apply_data_scope 一致：
    scope 2 本部门及子级 / 3 本部门 / 4 仅本人 / 5 自定义部门。
    """
    from app.modules.org.models import EmpDept, EmpUser
    from app.modules.rbac.models import SysAccountRole, SysRole, SysRoleDept

    roles = db.scalars(
        select(SysRole)
        .join(SysAccountRole, SysAccountRole.role_id == SysRole.id)
        .where(SysAccountRole.account_id == account.id)
    ).all()
    if not roles:
        return {"dept_ids": set(), "self_only": False, "deny": True}  # 无角色：fail-closed
    if any(r.code == "super_admin" or r.data_scope == 1 for r in roles):
        return None

    own_dept_id = None
    if account.emp_user_id:
        eu = db.get(EmpUser, account.emp_user_id)
        own_dept_id = eu.dept_id if eu else None

    dept_ids: set[int] = set()
    self_only = False
    for r in roles:
        if r.data_scope == 4:
            self_only = True
        elif r.data_scope in (2, 3) and own_dept_id:
            dept_ids.add(own_dept_id)
            if r.data_scope == 2:
                own = db.get(EmpDept, own_dept_id)
                if own:
                    dept_ids.update(
                        d.id for d in db.scalars(
                            select(EmpDept).where(EmpDept.path.like(f"{own.path.rstrip('/')}/%"))
                        ).all()
                    )
        elif r.data_scope == 5:
            dept_ids.update(
                did for did in db.scalars(
                    select(SysRoleDept.dept_id).where(SysRoleDept.role_id == r.id)
                ).all()
            )
    if not dept_ids and not self_only:
        return {"dept_ids": set(), "self_only": False, "deny": True}  # 有角色但条件无法落地
    return {"dept_ids": dept_ids, "self_only": self_only, "deny": False}


def _inject_scope(db: Session, account, sql: str) -> str:
    """按账号数据范围改写 SQL：员工/事件表追加部门或本人条件。

    口径与 core.deps.apply_data_scope 一致：部门与本人条件并存时按 OR 合并，
    有角色但条件无法落地时 fail-closed 拒绝。

    - emp_user（别名 u）→ u.dept_id IN (...)，仅本人 → u.id = <本人>
    - emp_risk_profile（无 dept_id 列，别名 p）→ p.user_id IN (SELECT id FROM emp_user WHERE dept_id IN (...))
    - campaign_target / track_event（别名 t）→ t.user_id IN (同子查询)
    - 无员工/事件表（campaign 聚合等）→ 不注入
    """
    scope = _scope_of(db, account)
    if scope is None:
        return sql  # 全量可见
    if scope.get("deny"):
        raise BizError(ErrorCode.PERM_DENIED, "当前账号无数据查询权限")

    dept_ids = sorted(scope["dept_ids"])
    self_only = scope["self_only"]
    if not dept_ids and not self_only:
        return sql
    dept_in = f"({', '.join(str(d) for d in dept_ids)})" if dept_ids else None
    own_uid = account.emp_user_id or -1

    def _user_cond(alias: str) -> str | None:
        """事件/画像表按别名追加：部门子查询或仅本人。"""
        if dept_ids:
            return f"{alias}.user_id IN (SELECT id FROM emp_user WHERE dept_id IN {dept_in})"
        if self_only:
            return f"{alias}.user_id = {own_uid}"
        return None

    try:
        sel = sqlglot.parse_one(sql, read="mysql")
    except Exception as exc:
        raise BizError(ErrorCode.PARAM_INVALID, "SQL 校验失败") from exc
    tables = {t.name.lower(): t.alias_or_name for t in sel.find_all(sqlglot.exp.Table)}

    conds: list[str] = []
    if "emp_user" in tables:
        if dept_ids:
            conds.append(f"{tables['emp_user']}.dept_id IN {dept_in}")
        if self_only:
            conds.append(f"{tables['emp_user']}.id = {own_uid}")
    if "emp_risk_profile" in tables:
        c = _user_cond(tables["emp_risk_profile"])
        if c:
            conds.append(c)
    for name in ("campaign_target", "track_event"):
        if name in tables:
            c = _user_cond(tables[name])
            if c:
                conds.append(c)

    if not conds:
        return sql
    cond = exp.or_(*conds) if len(conds) > 1 else exp.condition(conds[0])
    if sel.args.get("where"):
        cond = exp.and_(sel.args["where"].this, cond)
    return sel.where(cond).sql(dialect="mysql")


# ---------- 只读执行 ----------

_readonly_engine = None


def _get_readonly_engine():
    """独立只读账号引擎（生产配置 chatbi_readonly_dsn）；未配置返回 None 用主库只读事务。"""
    global _readonly_engine
    if _readonly_engine is None:
        dsn = get_settings().chatbi_readonly_dsn
        if dsn:
            _readonly_engine = create_engine(dsn, pool_pre_ping=True)
    return _readonly_engine


def _execute_readonly(sql: str) -> tuple[list[str], list[list]]:
    """只读执行：独立只读账号优先（chatbi_readonly_dsn）；未配置时主库只读事务兜底。

    MySQL：走 raw DBAPI 连接——`SET SESSION TRANSACTION READ ONLY` 必须在无活动
    事务时执行（事务中设置报 1568），而 SQLAlchemy autobegin 会在首条语句前开事务，
    故绕过 ORM 层。SQLite（测试环境）无只读事务语句，直接执行。
    """
    eng = _get_readonly_engine() or engine
    if eng.dialect.name == "sqlite":
        with eng.connect() as conn:
            result = conn.exec_driver_sql(sql)
            cols = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
            conn.commit()  # 结束读事务再归还连接：测试单连接池下避免读锁残留
            return cols, rows
    raw = eng.raw_connection()
    try:
        cur = raw.cursor()
        # 事务级只读（而非 SET SESSION）：事务结束自动恢复读写，不污染连接池
        # 复用（会话级 READ ONLY 残留会导致池内后续写报 1792）
        cur.execute("START TRANSACTION READ ONLY")
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        finally:
            cur.execute("COMMIT")  # 结束只读事务，连接归还池
    finally:
        raw.close()
    return cols, rows


# ---------- LLM 生成路径（红线 5 守卫不变，规则引擎兜底） ----------

_CHATBI_SCHEMA_HINT = """可查询的表（仅限以下，禁止任何其他表）：
- campaign(id,name,status,created_at) 演练
- campaign_target(campaign_id,user_id,batch_no,send_status,sent_at,submit_flag,attach_run_count,first_open_at,first_click_at,report_flag) 演练目标明细
- track_event(id,user_id,event_type,created_at) 追踪事件（event_type: open/click/submit/attach_run/report/bounce）
- emp_user(id,name,email,dept_id,status) 员工
- emp_dept(id,parent_id,name) 部门
- emp_risk_profile(user_id,total_score,risk_level,phish_count) 员工风险画像
- mail_report(id,reporter_user_id,classification,created_at) 邮件举报
- training_assignment(id,task_id,course_id,user_id,progress,status,assigned_at,completed_at) 培训任务（status: pending/learning/completed/overdue）
- course(id,title,type,duration_min,status) 课程

口径：中招 = submit_flag=1 OR attach_run_count>0；
培训通过率/完成率 = training_assignment.status='completed' 的占比。
约束：只输出一条 SELECT 语句，不得包含其他语句；表名仅限上述；必须带 LIMIT（≤200）；
时间筛选按给定的时间窗起点用 >= '起点时间' 表达；聚合用 COUNT/SUM/GROUP BY 即可。"""

_CHATBI_SYSTEM = (
    "你是 PhishLab 钓鱼演练平台的报表问数 SQL 生成器。根据用户问题生成单条只读 SELECT 查询。"
    "只输出 SQL 本身（可用 ```sql 代码块包裹），不要解释、不要补注释。"
    "严禁生成任何非 SELECT 语句（禁 INSERT/UPDATE/DELETE/DROP/ALTER/INTO）。"
)


def _extract_sql_text(text: str) -> str | None:
    """从 LLM 输出提取 SQL：优先 ```sql 代码块，否则取首个 SELECT 到结尾。"""
    m = re.search(r"```(?:sql)?\s*(SELECT.*?)```", text, re.S) or re.search(r"```\s*(SELECT.*?)```", text, re.S)
    if m:
        return m.group(1).strip()
    idx = text.upper().find("SELECT")
    return text[idx:].strip() if idx >= 0 else None


def _finalize_sql(sql: str, since: datetime) -> str:
    """时间窗字面量内联 + 方言转换（LLM 与规则引擎共用）。

    since 为本服务解析的 datetime，非用户输入，内联无注入面；
    不依赖绑定参数可避免 sqlglot 方言参数输出与 DBAPI 占位风格不匹配。
    """
    sel = sqlglot.parse_one(sql, read="mysql")
    for p in sel.find_all(exp.Placeholder):  # sqlglot 30 命名参数解析为 Placeholder
        if p.name == "since":
            p.replace(exp.Literal.string(since.strftime("%Y-%m-%d %H:%M:%S")))
    sql = sel.sql(dialect="mysql")
    write_dialect = engine.dialect.name
    if write_dialect != "mysql":
        sql = sqlglot.transpile(sql, read="mysql", write=write_dialect)[0]
    return sql


async def _ask_via_llm(db: Session, account, question: str, since: datetime) -> dict | None:
    """LLM 生成 SQL 并走完整安全管线（校验/注入/只读执行/用量）。

    任何环节失败（无 Provider / 输出非法 / 校验拒绝）返回 None，由调用方兜底规则引擎，
    保证问数能力不因 LLM 降级而失效。
    """
    from .llm import get_client, get_provider, record_usage

    provider = get_provider(db)
    if provider is None:
        return None
    client = get_client(db, provider)
    result = await client.chat(
        [{"role": "user", "content":
          f"用户问题：{question}\n当前时间：{datetime.now():%Y-%m-%d %H:%M}\n"
          f"时间窗起点（近30天/近N天/本月/上月按此推算）：{since:%Y-%m-%d %H:%M:%S}\n"
          f"{_CHATBI_SCHEMA_HINT}"}],
        system_prompt=provider.system_prompt or _CHATBI_SYSTEM,
        # 推理型模型（deepseek-v4-flash 等）会把思考过程计入输出 token，
        # 预留足够额度让最终 SQL 落进 content（800 会被 reasoning 耗尽）
        temperature=0.1, max_tokens=4096,
    )
    raw = _extract_sql_text(result.get("content") or "")
    if not raw:
        # content 为空（推理被 max_tokens 截断）时，从思考过程兜底提取
        raw = _extract_sql_text(result.get("reasoning_content") or "")
    if not raw:
        logger.warning("chatbi llm unparseable output provider=%s", provider.name)
        return None
    sql = _validate_sql(raw)  # 与规则引擎同一守卫：表白名单/单SELECT/禁INTO/强制LIMIT
    sql = _inject_scope(db, account, sql)
    sql = _finalize_sql(sql, since)
    cols, rows = _execute_readonly(sql)
    record_usage(db, provider, result.get("tokens_in"), result.get("tokens_out"))
    return {"title": "AI 问数", "sql": sql, "columns": cols,
            "rows": rows[:_MAX_ROWS], "total": len(rows)}


# ---------- 主入口 ----------


async def ask_question(db: Session, account, question: str) -> dict:
    """ChatBI 问数：规则引擎优先（毫秒级、结果确定），长尾问法走 LLM（同一安全管线）。

    管线：意图 → SQL（模板或 LLM）→ sqlglot 校验 → 权限注入 → 只读执行 → 审计。
    推理型模型（deepseek-v4-flash 等）单次调用需 20-60s，故已知问法不经 LLM。
    """
    question = (question or "").strip()
    if not question:
        raise BizError(ErrorCode.PARAM_INVALID, "请输入要查询的问题")
    if len(question) > 200:
        raise BizError(ErrorCode.PARAM_INVALID, "问题过长（≤200 字）")

    since = _parse_window(question)

    # 规则引擎优先：命中模板直接执行，不等待 LLM
    matched = _match_template(question)
    if matched is not None:
        title, raw_sql = matched
        try:
            sql = _validate_sql(raw_sql)
            sql = _inject_scope(db, account, sql)
        except BizError:
            raise
        except Exception as exc:  # 注入层意外失败 fail-closed，不执行
            logger.exception("chatbi sql guard failed")
            raise BizError(ErrorCode.PARAM_INVALID, "问数校验失败，已拒绝执行") from exc

        sql = _finalize_sql(sql, since)
        cols, rows = _execute_readonly(sql)

        record_audit(db, account=account, module="ai", action="chatbi_ask",
                     target_type="chatbi", detail={"question": question, "sql": sql,
                                                   "rows": len(rows), "llm": False})
        logger.info("chatbi ask account=%s rows=%d", account.id, len(rows))
        return {
            "question": question,
            "title": title,
            "sql": sql,
            "columns": cols,
            "rows": rows[: _MAX_ROWS],
            "total": len(rows),
        }

    # LLM 路径：未命中模板的长尾问法；任何异常降级为兜底报错，不阻断问数
    llm_result = None
    try:
        llm_result = await _ask_via_llm(db, account, question, since)
    except BizError as exc:
        logger.warning("chatbi llm path failed: %s", exc.message)
    except Exception:
        logger.exception("chatbi llm path unexpected failure")

    if llm_result is not None:
        record_audit(db, account=account, module="ai", action="chatbi_ask",
                     target_type="chatbi", detail={"question": question, "sql": llm_result["sql"],
                                                   "rows": llm_result["total"], "llm": True})
        logger.info("chatbi ask(llm) account=%s rows=%d", account.id, llm_result["total"])
        return {"question": question, **llm_result}

    raise BizError(ErrorCode.PARAM_INVALID,
                   "暂不支持该问法，可尝试：各部门中招率、近7天中招/举报趋势、"
                   "中招最多的员工、高危/高风险人员、各演练统计、举报最多的部门、"
                   "培训通过率最低的部门")
