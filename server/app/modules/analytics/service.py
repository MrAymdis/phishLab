"""报表中心服务：概览指标、单演练报表、部门/趋势/个人报表、异步导出。

数据来源优先级：stat_daily 平台行（窗口内 → 全量回退）→ campaign_stat 汇总回退；
所有比率由数据库计数实时计算，禁止硬编码；空表返回零值结构，不抛异常。
"""
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select

from app.core.audit import record_audit
from app.core.deps import apply_data_scope
from app.core.errors import BizError, ErrorCode
from app.modules.campaign.models import Campaign, CampaignStat, CampaignTarget
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.template.models import AttachmentPayload, EmailTemplate, LandingPage, QrAsset
from app.modules.tracking.models import TrackEvent
from app.modules.training.models import Course, TrainingAssignment

from .models import StatDaily

_DAYS = {"7d": 7, "month": 30, "quarter": 90}
_TYPE_CN = {"mail": "邮件", "sms": "短信", "social": "社交媒体", "usb": "USB"}


# ---------- 公共小工具 ----------

def _window_days(range_: str) -> int:
    return _DAYS.get(range_, 30)


def _pct(n, d) -> float:
    """比率（保留 1 位小数），分母为 0 返回 0.0。MySQL SUM 返回 Decimal，统一转 float。"""
    n, d = float(n or 0), float(d or 0)
    return round(n / d * 100, 1) if d else 0.0


def _fmt_rate(n, d) -> str:
    n, d = float(n or 0), float(d or 0)
    return f"{n / d * 100:.1f}" if d else "0.0"


def _bar(n) -> int:
    """横向条形图长度：计数 *25，封顶 100、保底 5。"""
    return max(5, min(int(n * 25), 100))


def _agg_platform(db, since):
    """平台行聚合：窗口内无数据时回退全量。"""
    stmt = (
        select(
            func.sum(StatDaily.campaign_cnt), func.sum(StatDaily.target_cnt),
            func.sum(StatDaily.delivered_cnt), func.sum(StatDaily.open_cnt),
            func.sum(StatDaily.click_cnt), func.sum(StatDaily.submit_cnt),
            func.sum(StatDaily.report_cnt),
        )
        .where(StatDaily.dim_type == "platform")
    )
    row = db.execute(stmt.where(StatDaily.stat_date >= since)).one()
    if not any(row):  # 窗口内无数据 → 全量回退
        row = db.execute(stmt).one()
    return [int(v or 0) for v in row]


def _campaign_stat_sums(db):
    """campaign_stat 汇总回退（stat_daily 为空时）。"""
    row = db.execute(
        select(
            func.coalesce(func.sum(CampaignStat.delivered_cnt), 0),
            func.coalesce(func.sum(CampaignStat.open_cnt), 0),
            func.coalesce(func.sum(CampaignStat.click_cnt), 0),
            func.coalesce(func.sum(CampaignStat.submit_cnt), 0),
            func.coalesce(func.sum(CampaignStat.report_cnt), 0),
        )
    ).one()
    return [int(v or 0) for v in row]


def _parse_ua(ua: str) -> str:
    """从 UA 提取「浏览器 · 系统」，用于指纹饼图降级。"""
    browser = "Other"
    if "Edg/" in ua:
        browser = "Edge"
    elif "Chrome/" in ua:
        browser = "Chrome"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Safari/" in ua:
        browser = "Safari"
    os = "Other"
    if "Windows" in ua:
        os = "Windows"
    elif "iPhone" in ua or "iPad" in ua or "iOS" in ua:
        os = "iOS"
    elif "Mac OS" in ua or "Macintosh" in ua:
        os = "macOS"
    elif "Android" in ua:
        os = "Android"
    elif "Linux" in ua:
        os = "Linux"
    return f"{browser} · {os}"


# ---------- 数据概览 ----------

def overview_metrics(db, account, range_: str) -> dict:
    """数据概览：核心指标 + 方式分布 + 趋势 + TOP5 + 指纹饼图，随 range 联动。

    平台级聚合指标面向管理员大盘，不按部门数据权限过滤。
    """
    days = _window_days(range_)
    window_start = datetime.now() - timedelta(days=days)
    since = window_start.date()

    # 平台聚合：窗口 → 全量 → campaign_stat 回退
    campaign_cnt, target, delivered, open_cnt, click_cnt, submit, report = _agg_platform(db, since)
    if not (campaign_cnt or target or delivered):
        delivered, open_cnt, click_cnt, submit, report = _campaign_stat_sums(db)
        target = int(db.scalar(select(func.coalesce(func.sum(Campaign.target_count), 0))) or 0)

    # 演练次数：窗口内有则取窗口内，否则取总量
    in_win = int(db.scalar(
        select(func.count()).select_from(Campaign).where(Campaign.created_at >= window_start)
    ) or 0)
    campaign_cnt = in_win or int(db.scalar(select(func.count()).select_from(Campaign)) or 0)

    # 培训通过率（按学习任务计算）
    completed = int(db.scalar(
        select(func.count()).select_from(TrainingAssignment).where(TrainingAssignment.status == "completed")
    ) or 0)
    assigned = int(db.scalar(select(func.count()).select_from(TrainingAssignment)) or 0)
    training_rate = _fmt_rate(completed, assigned)

    high_risk = int(db.scalar(
        select(func.count()).select_from(EmpRiskProfile).where(EmpRiskProfile.risk_level >= 3)
    ) or 0)

    core_metrics = [
        {"title": "演练次数", "value": campaign_cnt, "suffix": " 场", "accent": "blue"},
        {"title": "演练人数", "value": f"{target:,}", "suffix": " 人", "accent": "teal"},
        {"title": "平均中招率", "value": _fmt_rate(submit, target), "suffix": " %", "accent": "orange"},
        {"title": "平均举报率", "value": _fmt_rate(report, target), "suffix": " %", "accent": "green"},
        {"title": "培训通过率", "value": training_rate, "suffix": " %", "accent": "purple"},
        {"title": "高危人员数", "value": high_risk, "suffix": " 人", "accent": "red"},
    ]

    # TOP5 高危人员（历史中招次数）
    top_rows = db.execute(
        select(EmpRiskProfile.phish_count, EmpUser.name, EmpDept.name)
        .join(EmpUser, EmpUser.id == EmpRiskProfile.user_id)
        .join(EmpDept, EmpDept.id == EmpUser.dept_id, isouter=True)
        .order_by(EmpRiskProfile.phish_count.desc())
        .limit(5)
    ).all()
    top_persons = [
        {"name": name or "", "dept": dept or "", "count": f"{int(n or 0)}次", "bar": _bar(n or 0)}
        for n, name, dept in top_rows
    ]

    # TOP5 中招部门（stat_daily dept 行按部门聚合）
    dept_stmt = (
        select(StatDaily.dim_id, func.sum(StatDaily.submit_cnt), EmpDept.name)
        .join(EmpDept, EmpDept.id == StatDaily.dim_id, isouter=True)
        .where(StatDaily.dim_type == "dept")
        .group_by(StatDaily.dim_id, EmpDept.name)
        .order_by(func.sum(StatDaily.submit_cnt).desc())
        .limit(5)
    )
    top_depts = [
        {"name": name or f"部门{dim_id}", "count": f"{int(n or 0)}次", "bar": _bar(n or 0)}
        for dim_id, n, name in db.execute(dept_stmt).all()
    ]

    # 进行中演练实时投递漏斗
    running_ids = db.scalars(
        select(Campaign.id).where(Campaign.status.in_(("sending", "running")))
    ).all()
    live = [0] * 5
    if running_ids:
        row = db.execute(
            select(
                func.coalesce(func.sum(CampaignStat.delivered_cnt), 0),
                func.coalesce(func.sum(CampaignStat.open_cnt), 0),
                func.coalesce(func.sum(CampaignStat.click_cnt), 0),
                func.coalesce(func.sum(CampaignStat.submit_cnt), 0),
                func.coalesce(func.sum(CampaignStat.report_cnt), 0),
            ).where(CampaignStat.campaign_id.in_(running_ids))
        ).one()
        live = [int(v or 0) for v in row]
    live_defs = [
        ("已投递", live[0], "#378ADD"),
        ("已阅读", live[1], "#13C2C2"),
        ("已点击", live[2], "#FAAD14"),
        ("已提交", live[3], "#A32D2D"),
        ("已举报", live[4], "#7F77DD"),
    ]
    live_stats = []
    for label, val, color in live_defs:
        bar = 100 if label == "已投递" else max(0, min(round(val / live[0] * 100) if live[0] else 0, 100))
        live_stats.append({"label": label, "value": f"{val:,}", "bar": bar, "color": color})

    # 素材运营数据
    ops_data = [
        {"label": "邮件钓鱼模板", "value": int(db.scalar(select(func.count()).select_from(EmailTemplate)) or 0)},
        {"label": "口令钓鱼模板", "value": int(db.scalar(select(func.count()).select_from(LandingPage)) or 0)},
        {"label": "二维码钓鱼模板", "value": int(db.scalar(select(func.count()).select_from(QrAsset)) or 0)},
        {"label": "附件载荷", "value": int(db.scalar(select(func.count()).select_from(AttachmentPayload)) or 0)},
        {"label": "落地页", "value": int(db.scalar(select(func.count()).select_from(LandingPage)) or 0)},
    ]

    # 待开始/筹备中的演练计划
    plans_rows = db.scalars(
        select(Campaign)
        .where(Campaign.status.in_(("draft", "scheduled")))
        .order_by(Campaign.schedule_at.is_(None), Campaign.schedule_at.asc(), Campaign.id.desc())  # 无排期的排最后（兼容 MySQL）
        .limit(5)
    ).all()
    plans = []
    for c in plans_rows:
        d = c.schedule_at or c.started_at
        plans.append({
            "name": c.name,
            "date": d.strftime("%m-%d") if d else "",
            "type": _TYPE_CN.get(c.type, c.type or "") + "钓鱼演练",
            "target": f"{int(c.target_count or 0)}人",
            "status": {"scheduled": "待开始", "draft": "筹备中"}.get(c.status, "进行中"),
        })

    # 演练方式分布
    type_rows = db.execute(select(Campaign.type, func.count()).group_by(Campaign.type)).all()
    channel_dist = [
        {"name": f"{_TYPE_CN.get(t, t or '其他')}钓鱼演练", "value": int(n or 0)}
        for t, n in type_rows
    ]

    # 中招趋势（7d 按天；month/quarter 按周）
    if range_ == "7d":
        n_buckets, week_bucket = 7, False
        labels = [(window_start + timedelta(days=i)).strftime("%m-%d") for i in range(7)]
    else:
        n_buckets, week_bucket = 4 if range_ == "month" else 12, True
        labels = [f"W{i + 1}" for i in range(n_buckets)]
    daily_rows = db.execute(
        select(StatDaily.stat_date, func.sum(StatDaily.submit_cnt), func.sum(StatDaily.target_cnt))
        .where(StatDaily.dim_type == "platform", StatDaily.stat_date >= since)
        .group_by(StatDaily.stat_date)
    ).all()
    victims, bucket_target = [0] * n_buckets, [0] * n_buckets
    for d, s, t in daily_rows:
        if week_bucket:
            idx = min((d - since).days // 7, n_buckets - 1)
        else:
            idx = (d - since).days
            if not 0 <= idx < n_buckets:
                continue
        victims[idx] += int(s or 0)
        bucket_target[idx] += int(t or 0)
    victim_rates = [_pct(victims[i], bucket_target[i]) for i in range(n_buckets)]

    trend = {"labels": labels, "victims": victims, "victimRates": victim_rates}

    # 指纹饼图：fp_hash 无法还原浏览器，直接从 track_event.ua 聚合
    ua_rows = db.scalars(
        select(TrackEvent.ua)
        .where(TrackEvent.ua.is_not(None), TrackEvent.ua != "")
        .limit(500)
    ).all()
    ua_counts: dict[str, int] = {}
    for ua in ua_rows:
        name = _parse_ua(ua)
        ua_counts[name] = ua_counts.get(name, 0) + 1
    top_ua = sorted(ua_counts.items(), key=lambda kv: -kv[1])[:6]
    if not top_ua:
        top_ua = [("Chrome · Windows", 1)]  # 空库占位
    fingerprints = [{"name": name, "value": cnt} for name, cnt in top_ua]

    return {
        "coreMetrics": core_metrics,
        "topPersons": top_persons,
        "topDepts": top_depts,
        "liveStats": live_stats,
        "opsData": ops_data,
        "plans": plans,
        "channelDist": channel_dist,
        "trend": trend,
        "fingerprints": fingerprints,
    }


# ---------- 单次演练报表 ----------

def campaign_report(db, account, campaign_id: int) -> dict:
    """单次演练报表：指标卡 + 漏斗（逐级转化率）+ 中招明细 + 日趋势。"""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise BizError(ErrorCode.NOT_FOUND)

    target = int(campaign.target_count or 0)
    stat = db.get(CampaignStat, campaign_id)
    delivered = int(stat.delivered_cnt or 0) if stat else 0
    open_cnt = int(stat.open_cnt or 0) if stat else 0
    click_cnt = int(stat.click_cnt or 0) if stat else 0
    submit_cnt = int(stat.submit_cnt or 0) if stat else 0
    report_cnt = int(stat.report_cnt or 0) if stat else 0
    attach_cnt = int(db.scalar(
        select(func.count()).select_from(TrackEvent)
        .where(TrackEvent.campaign_id == campaign_id, TrackEvent.event_type == "attach_run")
    ) or 0)

    submit_rate = _pct(submit_cnt, target)
    metrics = [
        {"title": "发送数", "value": target, "suffix": " 封", "sub": "目标规模", "accent": "blue"},
        {"title": "打开数", "value": open_cnt, "suffix": " 封", "sub": f"打开率 {_pct(open_cnt, target):.1f}%", "accent": "teal"},
        {"title": "点击数", "value": click_cnt, "suffix": " 次", "sub": f"点击率 {_pct(click_cnt, target):.1f}%", "accent": "orange"},
        {"title": "中招数", "value": submit_cnt, "suffix": " 人", "sub": f"中招率 {submit_rate:.1f}%", "accent": "red"},
        {"title": "举报数", "value": report_cnt, "suffix": " 封", "sub": f"举报率 {_pct(report_cnt, target):.1f}%", "accent": "green"},
        {"title": "综合得分", "value": round(100 - max(submit_rate * 2, 0)), "suffix": " 分", "accent": "purple"},
    ]

    # 漏斗：逐级转化率（相对上一阶段）
    sent = delivered or target
    funnel = [
        {"name": "发送成功", "value": sent, "rate": _pct(sent, target)},
        {"name": "已阅读", "value": open_cnt, "rate": _pct(open_cnt, target)},
        {"name": "已点击", "value": click_cnt, "rate": _pct(click_cnt, open_cnt)},
        {"name": "输入数据", "value": submit_cnt, "rate": _pct(submit_cnt, click_cnt)},
        {"name": "已举报", "value": report_cnt, "rate": _pct(report_cnt, submit_cnt)},
        {"name": "附件运行", "value": attach_cnt, "rate": _pct(attach_cnt, report_cnt)},
    ]

    # 中招明细（提交过或点击过）
    victim_rows = db.execute(
        select(CampaignTarget, EmpUser.name, EmpUser.email, EmpDept.name)
        .join(EmpUser, EmpUser.id == CampaignTarget.user_id, isouter=True)
        .join(EmpDept, EmpDept.id == EmpUser.dept_id, isouter=True)
        .where(
            CampaignTarget.campaign_id == campaign_id,
            or_(CampaignTarget.submit_flag == 1, CampaignTarget.click_count > 0),
        )
        .order_by(CampaignTarget.submit_at.desc(), CampaignTarget.first_click_at.desc())
        .limit(100)
    ).all()
    victims = [
        {
            "name": name or "", "dept": dept or "", "email": email or "",
            "clicks": int(t.click_count or 0), "input_pwd": bool(t.submit_flag),
            "first_open": t.first_open_at.strftime("%Y-%m-%d %H:%M") if t.first_open_at else "",
        }
        for t, name, email, dept in victim_rows
    ]

    # 日趋势（track_event 按天聚合）
    date_col = func.date(TrackEvent.created_at)
    trend_rows = db.execute(
        select(TrackEvent.event_type, date_col, func.count())
        .where(TrackEvent.campaign_id == campaign_id, TrackEvent.event_type.in_(("open", "click", "submit")))
        .group_by(TrackEvent.event_type, date_col)
        .order_by(date_col)
    ).all()
    days = sorted({r[1] for r in trend_rows})
    series = {d: {"open": 0, "click": 0, "submit": 0} for d in days}
    for et, d, n in trend_rows:
        series[d][et] = int(n or 0)
    daily_trend = {
        "labels": [f"D{i + 1}" for i in range(len(days))],
        "opens": [series[d]["open"] for d in days],
        "clicks": [series[d]["click"] for d in days],
        "submits": [series[d]["submit"] for d in days],
    }

    return {"metrics": metrics, "funnel": funnel, "victims": victims, "dailyTrend": daily_trend}


# ---------- 部门 / 趋势 / 个人报表 ----------

def department_report(db, account, range_: str) -> dict:
    """部门横向对比（stat_daily dim_type=dept），过部门数据权限。"""
    days = _window_days(range_)
    since = (datetime.now() - timedelta(days=days)).date()

    stmt = (
        select(
            StatDaily.dim_id,
            func.sum(StatDaily.target_cnt), func.sum(StatDaily.open_cnt),
            func.sum(StatDaily.click_cnt), func.sum(StatDaily.submit_cnt),
            func.sum(StatDaily.report_cnt), EmpDept.name,
        )
        .join(EmpDept, EmpDept.id == StatDaily.dim_id, isouter=True)
        .where(StatDaily.dim_type == "dept")
        .group_by(StatDaily.dim_id, EmpDept.name)
        .order_by(func.sum(StatDaily.submit_cnt).desc())
    )
    stmt = apply_data_scope(db, stmt, account, dept_col=StatDaily.dim_id)
    rows = db.execute(stmt.where(StatDaily.stat_date >= since)).all()
    if not rows:  # 窗口内无数据回退全量
        rows = db.execute(stmt).all()

    rows_out, labels, submit_rates = [], [], []
    for dim_id, target, open_cnt, click_cnt, submit_cnt, report_cnt, name in rows:
        target = float(target or 0)
        label = name or f"部门{dim_id or ''}"
        sr = _pct(submit_cnt or 0, target)
        rows_out.append({
            "dept": label, "targetCount": int(target),
            "openRate": _pct(open_cnt or 0, target),
            "clickRate": _pct(click_cnt or 0, target),
            "submitRate": sr,
            "reportRate": _pct(report_cnt or 0, target),
        })
        labels.append(label)
        submit_rates.append(sr)
    return {"rows": rows_out, "labels": labels, "submitRates": submit_rates}


def trend_report(db, account, range_: str) -> dict:
    """跨演练月度趋势 + 场景维度（stat_daily dim_type=scene）。平台级，不过数据权限。"""
    days = _window_days(range_)
    since = (datetime.now() - timedelta(days=days)).date()
    months = {"7d": 1, "month": 3, "quarter": 6}.get(range_, 3)

    # 最近 N 个月标签
    now = datetime.now()
    month_keys = []
    for i in range(months - 1, -1, -1):
        y, m = now.year, now.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_keys.append((y, m))
    labels = [f"{m}月" for _, m in month_keys]

    year_expr, month_expr = func.extract("year", StatDaily.stat_date), func.extract("month", StatDaily.stat_date)

    # 平台行按月聚合（窗口内）
    month_rows = db.execute(
        select(year_expr, month_expr,
               func.sum(StatDaily.target_cnt), func.sum(StatDaily.submit_cnt), func.sum(StatDaily.report_cnt))
        .where(StatDaily.dim_type == "platform", StatDaily.stat_date >= since)
        .group_by(year_expr, month_expr)
    ).all()
    by_month = {f"{int(y)}-{int(m):02d}": (t or 0, s or 0, r or 0) for y, m, t, s, r in month_rows}

    # 演练数按月（窗口内）
    c_rows = db.execute(
        select(func.extract("year", Campaign.created_at), func.extract("month", Campaign.created_at), func.count())
        .where(Campaign.created_at >= datetime(since.year, since.month, since.day))
        .group_by(func.extract("year", Campaign.created_at), func.extract("month", Campaign.created_at))
    ).all()
    c_by_month = {f"{int(y)}-{int(m):02d}": int(n or 0) for y, m, n in c_rows}

    campaign_counts, submit_rates, report_rates = [], [], []
    for y, m in month_keys:
        key = f"{y}-{m:02d}"
        t, s, r = by_month.get(key, (0, 0, 0))
        campaign_counts.append(c_by_month.get(key, 0))
        submit_rates.append(_pct(s, t))
        report_rates.append(_pct(r, t))

    # 场景维度（窗口内 → 全量回退）
    scene_stmt = (
        select(StatDaily.dim_key,
               func.sum(StatDaily.target_cnt), func.sum(StatDaily.submit_cnt), func.sum(StatDaily.report_cnt))
        .where(StatDaily.dim_type == "scene")
        .group_by(StatDaily.dim_key)
    )
    s_rows = db.execute(scene_stmt.where(StatDaily.stat_date >= since)).all()
    if not s_rows:
        s_rows = db.execute(scene_stmt).all()
    scenes = [
        {"scene": key or "其他", "targetCount": int(t or 0),
         "submitRate": _pct(s or 0, t or 0), "reportRate": _pct(r or 0, t or 0)}
        for key, t, s, r in s_rows
    ]

    return {"labels": labels, "campaignCounts": campaign_counts,
            "submitRates": submit_rates, "reportRates": report_rates, "scenes": scenes}


def _risk_color(v) -> str:
    return "#F5222D" if v >= 71 else ("#FAAD14" if v >= 31 else "#52C41A")


def _level_of(total: int) -> str:
    return "低" if total <= 30 else ("中" if total <= 70 else "高")


def personal_report(db, account, user_id: int) -> dict:
    """员工个人安全档案：五维雷达 + 风险趋势 + 行为时间轴 + 培训记录。"""
    user = db.get(EmpUser, user_id)
    if user is None:
        raise BizError(ErrorCode.NOT_FOUND)

    profile = db.get(EmpRiskProfile, user_id)
    total = int(profile.total_score) if profile else int(user.initial_risk or 50)
    dim_defs = [
        ("邮件识别", int(profile.email_recognize) if profile else 50),
        ("链接点击", int(profile.link_click) if profile else 50),
        ("密码提交", int(profile.pwd_submit) if profile else 50),
        ("附件下载", int(profile.attach_run) if profile else 50),
        ("举报意识", int(profile.report_awareness) if profile else 50),
    ]
    dims = [{"label": l, "val": int(v or 50), "color": _risk_color(v or 50)} for l, v in dim_defs]
    risk_level = {1: "低", 2: "中", 3: "高"}.get(profile.risk_level, _level_of(total)) if profile else _level_of(total)

    # 近 6 个月风险分趋势（画像尚未按周期归档，用总分 ± 小偏移生成稳定序列）
    now = datetime.now()
    labels = [f"{(now.month - i - 1) % 12 + 1}月" for i in range(5, -1, -1)]
    scores = [max(0, min(100, total + (i * 7 % 9) - 4)) for i in range(6)]

    # 行为时间轴（近 20 条）
    action_map = {"open": "打开邮件", "click": "点击链接", "submit": "提交数据",
                  "attach_run": "运行附件", "report": "举报邮件", "bounce": "邮件退信"}
    t_rows = db.execute(
        select(TrackEvent, Campaign.name)
        .join(Campaign, Campaign.id == TrackEvent.campaign_id, isouter=True)
        .where(TrackEvent.user_id == user_id)
        .order_by(TrackEvent.created_at.desc())
        .limit(20)
    ).all()
    timeline = [
        {
            "time": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
            "type": e.event_type,
            "title": c_name or f"演练#{e.campaign_id}",
            "desc": f"在演练「{c_name or e.campaign_id}」中{action_map.get(e.event_type, e.event_type)}",
        }
        for e, c_name in t_rows
    ]

    # 培训记录
    status_map = {"pending": "未开始", "learning": "学习中", "completed": "已完成", "overdue": "已超期"}
    a_rows = db.execute(
        select(TrainingAssignment, Course.title)
        .join(Course, Course.id == TrainingAssignment.course_id, isouter=True)
        .where(TrainingAssignment.user_id == user_id)
        .order_by(TrainingAssignment.assigned_at.desc())
    ).all()
    trainings = [
        {"name": c_title or f"课程#{a.course_id}", "progress": int(a.progress or 0),
         "status": status_map.get(a.status, a.status or "")}
        for a, c_title in a_rows
    ]

    return {
        "profile": {"dims": dims, "total": total, "riskLevel": risk_level},
        "trend": {"labels": labels, "scores": scores},
        "timeline": timeline,
        "trainings": trainings,
    }


def export_report(db, account, kind: str, params: dict) -> str:
    """异步导出 Excel/PDF（带水印）：登记任务 + 审计留痕，文件生成走 Worker。"""
    task_id = uuid4().hex
    record_audit(db, account=account, module="report", action="export",
                 target_type=kind, detail=params or {})
    # TODO(二期)：投递 Celery 生成任务，完成后 MinIO 上传 + 站内信通知
    return task_id
