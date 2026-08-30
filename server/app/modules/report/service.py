"""邮件举报服务：插件上报 → 自动分类 → 人工研判闭环 + 积分奖励体系。

积分规则（platform_setting.report_reward_rules JSON，可编辑）：
- drill 演练邮件 +5 / real 真实钓鱼 +20 / first 首次举报 +10 / streak 连续正确举报每第3次 +3
演练命中（drill）自动分类即时发基础分；真实钓鱼研判后 TODO(二期) 联动 SIEM。
插件 API Key AES-GCM 加密入库（敏感配置红线），接口只回显掩码。
"""
import base64
import io
import json
import re
import secrets
import zipfile
from datetime import datetime, timedelta
from email import message_from_bytes, policy
from pathlib import Path

from sqlalchemy import func, or_, select

from app.core.audit import record_audit
from app.core.config import settings
from app.core.deps import apply_data_scope
from app.core.errors import BizError, ErrorCode
from app.core.security import decrypt_secret, encrypt_secret
from app.modules.channel.models import SenderProfile
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.settings.models import PlatformSetting
from app.modules.settings.service import get_setting

from .models import MailReport, ReportRedemption, ReportRewardItem, ReportRewardLog

VALID_CLASSIFICATION = ("drill", "real_phishing", "false_positive", "spam")
# 列表「自动识别/人工研判」两列的展示映射
_CLASS_MAP = {"drill": "drill", "real_phishing": "real", "false_positive": "false", "spam": "false", "pending": ""}
DEFAULT_DRILL_DOMAIN = "drill.phishlab.cn"

# 插件 API 配置键
_SETTING_API_KEY = "report_plugin_api_key"      # AES-GCM 密文
_SETTING_DOMAINS = "report_plugin_domains"      # JSON list
_SETTING_WEBHOOK = "report_webhook_url"
_SETTING_AUTOCLASS = "report_autoclass"         # "1"/"0"
_SETTING_NOTIFY = "report_notify_channels"      # JSON {"wecom":1,"dingtalk":0,"feishu":1}

# 默认积分规则（与前端原型一致）
_DEFAULT_RULES = [
    {"type": "drill", "name": "演练邮件", "points": 5, "desc": "成功识别并举报演练钓鱼邮件"},
    {"type": "real", "name": "真实钓鱼", "points": 20, "desc": "举报真实钓鱼邮件，消除安全隐患"},
    {"type": "first", "name": "首次举报", "points": 10, "desc": "员工首次参与举报的额外奖励"},
    {"type": "streak", "name": "连续举报", "points": 3, "desc": "连续3次正确举报，每次额外奖励"},
]


# ---------- 积分规则 ----------

def _set_setting(db, key: str, value: str) -> None:
    row = db.get(PlatformSetting, key)
    if row is None:
        row = PlatformSetting(setting_key=key)
        db.add(row)
    row.setting_value = value


def get_reward_rules(db) -> list[dict]:
    """积分规则列表（平台设置 JSON，未配置回落默认值）。"""
    raw = get_setting(db, "report_reward_rules", None)
    if raw:
        try:
            items = json.loads(raw)
            if isinstance(items, list) and items:
                return items
        except (json.JSONDecodeError, TypeError):
            pass
    return _DEFAULT_RULES


def _rule_map(db) -> dict[str, int]:
    return {i["type"]: int(i["points"]) for i in get_reward_rules(db)}


def update_reward_rules(db, account, rules: list[dict]) -> list[dict]:
    """保存积分规则（结构校验：type/name/points/desc）。"""
    clean = []
    seen: set[str] = set()
    for r in rules:
        t = str(r.get("type") or "").strip()
        if not t or t in seen or t not in ("drill", "real", "first", "streak"):
            raise BizError(ErrorCode.PARAM_INVALID, f"规则类型不合法：{t or '空'}")
        seen.add(t)
        try:
            points = int(r.get("points") or 0)
        except (TypeError, ValueError):
            raise BizError(ErrorCode.PARAM_INVALID, "奖励积分必须为整数")
        if points < 0 or points > 10000:
            raise BizError(ErrorCode.PARAM_INVALID, "奖励积分超出范围（0-10000）")
        clean.append({"type": t, "name": str(r.get("name") or "").strip() or t,
                      "points": points, "desc": str(r.get("desc") or "")})
    _set_setting(db, "report_reward_rules", json.dumps(clean, ensure_ascii=False))
    db.commit()
    record_audit(db, account=account, module="report", action="update_reward_rules",
                 target_type="report_reward_rules", detail={"rules": clean})
    return clean


def _grant(db, user_id, report_id, points: int, reason: str) -> None:
    if not user_id or points <= 0:
        return
    db.add(ReportRewardLog(user_id=user_id, report_id=report_id, points=points, reason=reason))


def _apply_reward(db, user_id, report_id, classification: str) -> int:
    """按规则发放积分：基础分 + 首次举报 + 连续正确举报每第3次；同一举报只发一次。"""
    if user_id is None or classification not in ("drill", "real_phishing"):
        return 0
    if db.scalar(select(func.count()).select_from(ReportRewardLog)
                 .where(ReportRewardLog.report_id == report_id)):
        return 0  # 已发过（自动分类已发基础分的场景），不重复发放
    rules = _rule_map(db)
    base = rules.get("drill" if classification == "drill" else "real", 0)

    # 首次举报：该用户此前没有任何举报记录
    prior = int(db.scalar(select(func.count()).select_from(MailReport)
                          .where(MailReport.reporter_user_id == user_id,
                                 MailReport.id != report_id)) or 0)
    if prior == 0:
        base += rules.get("first", 0)

    # 连续正确举报：正确举报总数每满 3 的倍数额外 +streak
    correct_cnt = int(db.scalar(select(func.count()).select_from(MailReport).where(
        MailReport.reporter_user_id == user_id,
        MailReport.classification.in_(("drill", "real_phishing")),
        MailReport.id != report_id,
    )) or 0)
    streak = rules.get("streak", 0)
    if streak and (correct_cnt + 1) % 3 == 0:
        base += streak

    _grant(db, user_id, report_id, base,
           {"drill": "演练邮件举报", "real_phishing": "真实钓鱼举报"}[classification])
    return base


# ---------- 举报中心 ----------

def report_stats(db) -> dict:
    """举报中心统计卡 + 分类计数（供筛选标签）。"""
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = int(db.scalar(select(func.count()).select_from(MailReport)) or 0)
    month_cnt = int(db.scalar(select(func.count()).select_from(MailReport)
                              .where(MailReport.created_at >= month_start)) or 0)
    real_cnt = int(db.scalar(select(func.count()).select_from(MailReport)
                             .where(MailReport.classification == "real_phishing")) or 0)
    false_cnt = int(db.scalar(select(func.count()).select_from(MailReport)
                              .where(MailReport.classification.in_(("false_positive", "spam")))) or 0)
    drill_cnt = int(db.scalar(select(func.count()).select_from(MailReport)
                              .where(MailReport.classification == "drill")) or 0)
    pending_cnt = int(db.scalar(select(func.count()).select_from(MailReport)
                                 .where(MailReport.classification == "pending")) or 0)
    return {
        "total": total,
        "monthCount": month_cnt,
        "realCount": real_cnt,
        "falseCount": false_cnt,
        "drillCount": drill_cnt,
        "pendingCount": pending_cnt,
        "misreportRate": round(false_cnt / total * 100, 1) if total else 0.0,
    }


def list_reports(db, account, *, classification=None, page=1, page_size=20,
                 kw: str | None = None, start_date: str | None = None,
                 end_date: str | None = None) -> dict:
    """举报列表：分类/关键词/时间范围筛选 + 分页；补充举报人/部门信息（批量避免 N+1）。"""
    conds = []
    if classification:
        conds.append(MailReport.classification == classification)
    if kw:
        like = f"%{kw.strip()}%"
        conds.append(or_(MailReport.subject.like(like), MailReport.from_addr.like(like),
                         MailReport.reporter_email.like(like)))
    if start_date:
        conds.append(MailReport.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        conds.append(MailReport.created_at < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))

    count_stmt = select(func.count()).select_from(MailReport).outerjoin(
        EmpUser, EmpUser.id == MailReport.reporter_user_id)
    stmt = select(MailReport).outerjoin(EmpUser, EmpUser.id == MailReport.reporter_user_id).order_by(MailReport.id.desc())
    if conds:
        count_stmt = count_stmt.where(*conds)
        stmt = stmt.where(*conds)
    # 数据权限：按举报人部门/本人过滤（reporter_user_id 为 emp_user id）
    count_stmt = apply_data_scope(db, count_stmt, account, dept_col=EmpUser.dept_id,
                                  self_id=MailReport.reporter_user_id)
    stmt = apply_data_scope(db, stmt, account, dept_col=EmpUser.dept_id,
                            self_id=MailReport.reporter_user_id)
    total = int(db.scalar(count_stmt) or 0)
    reports = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    # 批量补员工/部门
    user_ids = {r.reporter_user_id for r in reports if r.reporter_user_id}
    users = {u.id: u for u in db.scalars(select(EmpUser).where(EmpUser.id.in_(user_ids))).all()} if user_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d for d in db.scalars(select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}

    items = []
    for r in reports:
        user = users.get(r.reporter_user_id)
        mapped = _CLASS_MAP.get(r.classification, "")
        items.append({
            "id": r.id,
            "time": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            "subject": r.subject or "",
            "sender": r.from_addr or "",
            "reporter": (user.name if user else None) or r.reporter_email or "",
            "reporterDept": depts[user.dept_id].name if user and user.dept_id in depts else "",
            "auto": mapped,
            "manual": mapped if r.classifier == "manual" else "",
            "classification": r.classification,
            "remark": r.handle_remark or "",
            "rewardPoints": int(r.reward_points or 0),
            "channel": r.channel or "",
            "headers": r.headers or "",
            "messageId": r.message_id or "",
            "hasEml": bool(r.eml_path),
        })
    return {"list": items, "total": total, "page": page, "pageSize": page_size}


def classify(db, account, report_id: int, classification: str, remark: str | None = None):
    """人工研判：drill/real_phishing/false_positive/spam；正确研判发积分，真实钓鱼 TODO SIEM。"""
    if classification not in VALID_CLASSIFICATION:
        raise BizError(ErrorCode.PARAM_INVALID)
    # 数据权限过滤（与举报列表同口径：按举报人部门/本人），禁止跨范围研判
    # outerjoin：插件上报可能未关联员工（reporter_user_id IS NULL），内连接会丢行
    report = db.scalar(apply_data_scope(
        db, select(MailReport)
        .outerjoin(EmpUser, EmpUser.id == MailReport.reporter_user_id)
        .where(MailReport.id == report_id),
        account,
        dept_col=EmpUser.dept_id, self_id=MailReport.reporter_user_id,
    ))
    if report is None:
        raise BizError(ErrorCode.NOT_FOUND)

    report.classification = classification
    report.classifier = "manual"
    report.handler_id = account.id
    report.handled_at = datetime.now()
    report.handle_remark = remark

    points = _apply_reward(db, report.reporter_user_id, report.id, classification)
    if points:
        report.reward_points = int(report.reward_points or 0) + points
        # 风险画像举报意识加分
        profile = db.get(EmpRiskProfile, report.reporter_user_id)
        if profile is None:
            profile = EmpRiskProfile(user_id=report.reporter_user_id, total_score=50)
            db.add(profile)
        profile.report_count = int(profile.report_count or 0) + 1
    elif classification == "real_phishing":
        pass  # TODO(二期)：SIEM 推送

    db.commit()
    record_audit(db, account=account, module="report", action="classify",
                 target_id=str(report_id), detail={"classification": classification, "points": points})
    return {"id": report_id, "classification": classification, "points": points}


# ---------- 举报奖励 ----------

def ranking(db, top: int = 20) -> dict:
    """积分排行榜（本月 + 累计），按本月积分降序；徽章按成绩推导。"""
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month_stmt = (
        select(ReportRewardLog.user_id, func.sum(ReportRewardLog.points).label("m"))
        .where(ReportRewardLog.created_at >= month_start)
        .group_by(ReportRewardLog.user_id)
    )
    total_stmt = (
        select(ReportRewardLog.user_id, func.sum(ReportRewardLog.points).label("t"))
        .group_by(ReportRewardLog.user_id)
    )
    month_map = {uid: int(m or 0) for uid, m in db.execute(month_stmt).all()}
    total_map = {uid: int(t or 0) for uid, t in db.execute(total_stmt).all()}

    # 本月举报次数 + 真实钓鱼举报标记
    rpt_stmt = (
        select(MailReport.reporter_user_id, func.count(MailReport.id))
        .where(MailReport.reporter_user_id.is_not(None), MailReport.created_at >= month_start)
        .group_by(MailReport.reporter_user_id)
    )
    real_stmt = (
        select(MailReport.reporter_user_id)
        .where(MailReport.reporter_user_id.is_not(None),
               MailReport.classification == "real_phishing")
        .distinct()
    )
    rpt_map = {uid: int(n or 0) for uid, n in db.execute(rpt_stmt).all()}
    real_users = {uid for (uid,) in db.execute(real_stmt).all()}

    user_ids = set(month_map) | set(total_map)
    users = {u.id: u for u in db.scalars(select(EmpUser).where(EmpUser.id.in_(user_ids))).all()} if user_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d for d in db.scalars(select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}

    rows = []
    for uid in sorted(user_ids, key=lambda u: -month_map.get(u, 0)):
        u = users.get(uid)
        rows.append({
            "userId": uid,
            "name": u.name if u else f"用户#{uid}",
            "dept": depts[u.dept_id].name if u and u.dept_id in depts else "",
            "reportCount": rpt_map.get(uid, 0),
            "monthPoints": month_map.get(uid, 0),
            "totalPoints": total_map.get(uid, 0),
        })
    rows = rows[:top]
    for i, row in enumerate(rows):
        badges = []
        if i == 0 and row["monthPoints"] > 0:
            badges.append("月度冠军")
        if row["userId"] in real_users:
            badges.append("真实猎手")
        if row["totalPoints"] >= 500:
            badges.append("举报达人")
        if row["monthPoints"] >= 300:
            badges.append("火眼金睛")
        row["rank"] = i + 1
        row["badges"] = badges[:2]
    return {"list": rows, "total": len(rows)}


def points_overview(db) -> dict:
    """平台积分概览：累计/本月发放、参与人数 + 最近兑换记录。"""
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_issued = int(db.scalar(select(func.coalesce(func.sum(ReportRewardLog.points), 0))) or 0)
    month_issued = int(db.scalar(select(func.coalesce(func.sum(ReportRewardLog.points), 0))
                                 .where(ReportRewardLog.created_at >= month_start)) or 0)
    participants = int(db.scalar(select(func.count(func.distinct(ReportRewardLog.user_id)))) or 0)

    items = []
    red_rows = db.execute(
        select(ReportRedemption, ReportRewardItem.name, EmpUser.name)
        .join(ReportRewardItem, ReportRewardItem.id == ReportRedemption.item_id, isouter=True)
        .join(EmpUser, EmpUser.id == ReportRedemption.user_id, isouter=True)
        .order_by(ReportRedemption.id.desc())
        .limit(20)
    ).all()
    for r, item_name, user_name in red_rows:
        items.append({
            "id": r.id,
            "user": user_name or f"用户#{r.user_id}",
            "item": item_name or f"奖品#{r.item_id}",
            "points": int(r.points or 0),
            "time": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
        })
    return {"totalIssued": total_issued, "monthIssued": month_issued,
            "participants": participants, "redemptions": items}


def reward_catalog(db) -> list[dict]:
    """兑换商品目录（含库存）。"""
    items = db.scalars(select(ReportRewardItem).where(ReportRewardItem.enabled == 1)
                       .order_by(ReportRewardItem.id)).all()
    return [{"id": i.id, "name": i.name, "icon": i.icon or "", "cost": int(i.cost or 0),
             "stock": int(i.stock or 0)} for i in items]


def redeem(db, account, user_id: int, item_id: int) -> dict:
    """员工积分兑换：校验积分余额 → 扣库存 → 写兑换记录（全程审计）。"""
    user = db.get(EmpUser, user_id)
    if user is None:
        raise BizError(ErrorCode.NOT_FOUND, "员工不存在")
    item = db.get(ReportRewardItem, item_id)
    if item is None or not item.enabled:
        raise BizError(ErrorCode.NOT_FOUND, "奖品不存在或已下架")
    if item.cost <= 0:
        raise BizError(ErrorCode.BIZ_CONFLICT, "该奖品自动发放，无需兑换")
    if int(item.stock or 0) <= 0:
        raise BizError(ErrorCode.BIZ_CONFLICT, "奖品库存不足")

    earned = int(db.scalar(select(func.coalesce(func.sum(ReportRewardLog.points), 0))
                           .where(ReportRewardLog.user_id == user_id)) or 0)
    spent = int(db.scalar(select(func.coalesce(func.sum(ReportRedemption.points), 0))
                          .where(ReportRedemption.user_id == user_id)) or 0)
    if earned - spent < item.cost:
        raise BizError(ErrorCode.BIZ_CONFLICT,
                       f"积分不足：当前可用 {earned - spent} 分，需要 {item.cost} 分")

    item.stock -= 1
    db.add(ReportRedemption(user_id=user_id, item_id=item_id, points=item.cost))
    db.commit()
    record_audit(db, account=account, module="report", action="redeem",
                 target_type="report_reward_item", target_id=str(item_id),
                 detail={"user_id": user_id, "item": item.name, "points": item.cost})
    return {"ok": True, "points": item.cost, "item": item.name, "remaining": earned - spent - item.cost}


# ---------- 插件配置与鉴权 ----------

def _mask_key(key: str) -> str:
    return f"{key[:4]}****{key[-4:]}" if len(key) > 8 else "****"


def _plugin_domains(db) -> list[str]:
    """插件允许域名列表（平台设置 JSON，未配置/脏数据回空列表）。"""
    try:
        return json.loads(get_setting(db, _SETTING_DOMAINS, "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def get_plugin_config(db) -> dict:
    """插件 API 配置回显：Key 只回显掩码，其余为平台设置。"""
    enc = get_setting(db, _SETTING_API_KEY, None)
    key = decrypt_secret(enc.encode("latin1")) if enc else ""
    domains = _plugin_domains(db)
    try:
        notify = json.loads(get_setting(db, _SETTING_NOTIFY, '{"wecom":1,"dingtalk":0,"feishu":1}') or "{}")
    except (json.JSONDecodeError, TypeError):
        notify = {}
    return {
        "apiKeyMasked": _mask_key(key) if key else "",
        "allowedDomains": domains,
        "webhookUrl": get_setting(db, _SETTING_WEBHOOK, "") or "",
        "autoclass": (get_setting(db, _SETTING_AUTOCLASS, "1") or "1") == "1",
        "notifyChannels": {"wecom": bool(notify.get("wecom", 1)),
                           "dingtalk": bool(notify.get("dingtalk", 0)),
                           "feishu": bool(notify.get("feishu", 1))},
    }


def update_plugin_config(db, account, payload: dict) -> dict:
    """保存插件配置（域名白名单/Webhook/自动分类/通知渠道；Key 走重生成接口）。"""
    domains = [str(d).strip().lstrip("@").lower() for d in (payload.get("allowedDomains") or []) if str(d).strip()]
    webhook = str(payload.get("webhookUrl") or "").strip()
    _set_setting(db, _SETTING_DOMAINS, json.dumps(domains, ensure_ascii=False))
    _set_setting(db, _SETTING_WEBHOOK, webhook)
    _set_setting(db, _SETTING_AUTOCLASS, "1" if payload.get("autoclass") else "0")
    notify = payload.get("notifyChannels") or {}
    _set_setting(db, _SETTING_NOTIFY, json.dumps({
        "wecom": 1 if notify.get("wecom") else 0,
        "dingtalk": 1 if notify.get("dingtalk") else 0,
        "feishu": 1 if notify.get("feishu") else 0,
    }))
    db.commit()
    record_audit(db, account=account, module="report", action="update_plugin_config",
                 target_type="report_plugin", detail={"domains": domains, "webhook": webhook})
    return get_plugin_config(db)


def export_plugin_config(db, account, base_url: str) -> dict:
    """导出插件引导配置（serverUrl + 明文 API Key）：敏感出库走审计（红线 2 取证口径）。

    插件客户端首次使用时导入该 JSON（不随安装包分发 Key，每客户独立导出）。
    """
    enc = get_setting(db, _SETTING_API_KEY, None)
    if not enc:
        raise BizError(ErrorCode.NOT_FOUND, "插件 API Key 尚未生成，请先在「插件配置」中重生成")
    cfg = {
        "serverUrl": (base_url or "").rstrip("/"),
        "apiKey": decrypt_secret(enc.encode("latin1")),
        "allowedDomains": _plugin_domains(db),
        "version": "1.0",
    }
    record_audit(db, account=account, module="report", action="export_plugin_config",
                 target_type="report_plugin", detail={"domains": cfg["allowedDomains"]})
    return cfg


def regenerate_plugin_key(db, account) -> dict:
    """重生成插件 API Key：AES-GCM 加密入库（红线），回显掩码。"""
    key = "plr_" + secrets.token_urlsafe(32)
    _set_setting(db, _SETTING_API_KEY, encrypt_secret(key).decode("latin1"))
    db.commit()
    record_audit(db, account=account, module="report", action="regen_plugin_key",
                 target_type="report_plugin")
    return {"apiKeyMasked": _mask_key(key)}


def verify_plugin_key(db, provided: str | None) -> bool:
    """插件上报鉴权：X-Api-Key 与平台存储密钥比对（未配置即拒绝）。"""
    if not provided:
        return False
    enc = get_setting(db, _SETTING_API_KEY, None)
    if not enc:
        return False
    try:
        return secrets.compare_digest(decrypt_secret(enc.encode("latin1")), provided.strip())
    except Exception:
        return False


def test_plugin_webhook(db, webhook: str | None = None) -> dict:
    """Webhook 测试连接：向目标地址 POST 测试载荷，5 秒超时。"""
    import httpx
    url = (webhook or get_setting(db, _SETTING_WEBHOOK, "") or "").strip()
    if not url:
        raise BizError(ErrorCode.PARAM_INVALID, "请先配置 Webhook 回调 URL")
    try:
        r = httpx.post(url, json={"event": "phishlab_test", "ts": datetime.now().isoformat()},
                       timeout=5.0)
        return {"ok": r.status_code < 400, "status": r.status_code, "message": f"HTTP {r.status_code}"}
    except Exception as err:
        return {"ok": False, "status": 0, "message": f"连接失败：{err}"}


# ---------- 插件资产托管 ----------

PLUGIN_ASSETS_DIR = Path(__file__).resolve().parent / "plugin_assets"


def build_outlook_manifest(base_url: str) -> str:
    """Outlook Web Add-in manifest 动态生成：SourceLocation/图标必须客户可达，注入 base URL。"""
    base = base_url.rstrip("/")
    tpl = (PLUGIN_ASSETS_DIR / "outlook" / "manifest.template.xml").read_text(encoding="utf-8")
    return tpl.replace("{BASE}", base + "/")


def build_webmail_zip() -> bytes:
    """webmail/ 目录运行时打包 zip：MV3 扩展安装包（API Key 由配置 JSON 导入，不进包）。"""
    buf = io.BytesIO()
    root = PLUGIN_ASSETS_DIR / "webmail"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(root).as_posix())
    return buf.getvalue()


# ---------- 插件上报 ----------

_EML_MAX_BYTES = 8 * 1024 * 1024       # EML 解码后上限（base64 约 10.7MB）
_EML_HEADERS_CAP = 64 * 1024           # 邮件头回填上限
_EML_BODY_CAP = 20 * 1024              # 预览正文截断


def _get_scoped_report(db, account, report_id: int) -> MailReport | None:
    """按数据权限取单条举报（与列表/研判同口径：按举报人部门/本人）。"""
    return db.scalar(apply_data_scope(
        db, select(MailReport)
        .outerjoin(EmpUser, EmpUser.id == MailReport.reporter_user_id)
        .where(MailReport.id == report_id),
        account,
        dept_col=EmpUser.dept_id, self_id=MailReport.reporter_user_id,
    ))


def _save_eml(db, report: MailReport, eml_b64: str | None) -> str | None:
    """EML base64 落盘（static/report_eml/{id}.eml）并从归档解析邮件头回填 headers。

    非法 base64 / 超限 / 不像邮件的内容静默跳过——不阻断上报（Web 邮箱与老客户端走元数据模式）。
    """
    if not eml_b64:
        return None
    try:
        raw = base64.b64decode(eml_b64, validate=True)
    except Exception:
        return None
    # 轻校验：必须有邮件头块（冒号分隔），拦截随机 base64 垃圾
    if not raw or len(raw) > _EML_MAX_BYTES or b"\n" not in raw[:4096] or b":" not in raw.split(b"\n")[0]:
        return None
    try:
        msg = message_from_bytes(raw)
    except Exception:
        return None
    rel = f"report_eml/{report.id}.eml"
    abs_path = Path(settings.static_dir) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(raw)
    # 邮件头回填：旧客户端拿不到 internetHeaders 时由 EML 补齐（客户端显式上报的优先）
    headers = "\n".join(f"{k}: {v}" for k, v in msg.items())[:_EML_HEADERS_CAP]
    if headers and not report.headers:
        report.headers = headers
    return rel


def report_preview(db, account, report_id: int) -> dict:
    """举报邮件预览：从 EML 归档解析（正文截断 + 附件清单）；无归档回空结构。"""
    report = _get_scoped_report(db, account, report_id)
    if report is None:
        raise BizError(ErrorCode.NOT_FOUND)
    base = {
        "hasEml": bool(report.eml_path), "emlSize": 0,
        "from": report.from_addr or "", "subject": report.subject or "",
        "to": "", "date": "", "body": "", "attachments": [],
    }
    if not report.eml_path:
        return base
    path = Path(settings.static_dir) / report.eml_path
    if not path.is_file():
        return base
    raw = path.read_bytes()
    base["emlSize"] = len(raw)
    try:
        msg = message_from_bytes(raw, policy=policy.default)
    except Exception:
        return base
    base.update({
        "from": str(msg.get("From") or report.from_addr or ""),
        "subject": str(msg.get("Subject") or report.subject or ""),
        "to": str(msg.get("To") or ""),
        "date": str(msg.get("Date") or ""),
    })
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is not None:
        text = str(body.get_content() or "")
        if body.get_content_type() == "text/html":
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
        base["body"] = text.strip()[:_EML_BODY_CAP]
    for part in msg.iter_attachments():
        name = part.get_filename() or "未命名附件"
        size = len(part.get_payload(decode=True) or b"")
        base["attachments"].append({"name": name, "size": size})
    return base


def report_eml_path(db, account, report_id: int) -> Path | None:
    """EML 原件路径（数据权限 + 文件存在双校验），无归档回 None。"""
    report = _get_scoped_report(db, account, report_id)
    if report is None or not report.eml_path:
        return None
    path = Path(settings.static_dir) / report.eml_path
    return path if path.is_file() else None


def ingest_from_plugin(db, payload: dict) -> int:
    """插件上报入口（API Key 鉴权在路由层）：落库 → 自动分类 → 演练命中即时发基础分。"""
    from_addr = payload.get("from_addr")
    reporter_email = payload.get("reporter_email")

    # 域名白名单：配置后强制校验（fail-closed，防 Key 泄漏后冒用任意邮箱上报），未配置放行
    domains = _plugin_domains(db)
    if domains and not (
        reporter_email and any(reporter_email.lower().endswith("@" + d.lower()) for d in domains)
    ):
        raise BizError(ErrorCode.PARAM_INVALID, "举报人邮箱域名未在插件允许列表中，请联系管理员")
    # 重复上报：同 message_id 只收一次（插件端幂等友好提示）
    message_id = payload.get("message_id")
    if message_id and db.scalar(
        select(MailReport.id).where(MailReport.message_id == message_id).limit(1)
    ):
        raise BizError(ErrorCode.BIZ_CONFLICT, "该邮件已举报过，感谢您的反馈")

    # 自动分类：演练域名后缀或已配置伪装发件人 → drill；其余默认真实钓鱼待研判
    classification = "real_phishing"
    autoclass = (get_setting(db, _SETTING_AUTOCLASS, "1") or "1") == "1"
    if autoclass and from_addr:
        drill_domain = (get_setting(db, "drill_domain", DEFAULT_DRILL_DOMAIN) or DEFAULT_DRILL_DOMAIN).strip().lower()
        if from_addr.lower().endswith(drill_domain):
            classification = "drill"
        elif db.scalar(
            select(func.count()).select_from(SenderProfile)
            .where(func.lower(SenderProfile.from_addr) == from_addr.lower())
        ):
            classification = "drill"

    reporter_user_id = None
    if reporter_email:
        user = db.scalar(select(EmpUser).where(EmpUser.email == reporter_email))
        reporter_user_id = user.id if user else None

    report = MailReport(
        channel=payload.get("channel") or "outlook_plugin",
        reporter_user_id=reporter_user_id,
        reporter_email=reporter_email,
        message_id=message_id,
        from_addr=from_addr,
        subject=payload.get("subject"),
        headers=payload.get("headers"),
        classification=classification,
        classifier="auto",
        matched_campaign_id=None,  # TODO(二期)：按 Message-ID/token 精确匹配演练
    )
    db.add(report)
    db.flush()
    # EML 全文归档（新 Outlook getAsFileAsync 提供）：落盘 + 邮件头回填，失败静默降级
    report.eml_path = _save_eml(db, report, payload.get("eml_base64"))
    points = 0
    if classification == "drill" and reporter_user_id:
        points = _rule_map(db).get("drill", 0)
        report.reward_points = points
        _grant(db, reporter_user_id, report.id, points, "演练邮件举报")
    db.commit()
    db.refresh(report)
    # Webhook 告警推送：员工举报（推送失败不阻断入库）
    try:
        from app.modules.integration.service import notify_webhooks

        notify_webhooks(db, "report", {
            "发件人": from_addr or "-",
            "主题": payload.get("subject") or "-",
            "举报人": reporter_email or "-",
            "自动分类": "演练邮件" if classification == "drill" else "疑似真实钓鱼",
        })
    except Exception:
        pass
    return report.id
