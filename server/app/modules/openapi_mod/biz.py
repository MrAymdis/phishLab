"""开放平台业务端点实现（三期模块）。

查询口径与内部报表保持一致（41bab24 全局合并口径）：中招 = 提交 + 附件运行；
漏斗/指标卡语义同 analytics 模块。数据可见性：应用 scope 授权即客户全量数据
可见（无平台账号部门上下文），scope 由网关层校验控制端点可达性——本层不做
二次权限判断，全部直查。
"""
from datetime import datetime, timedelta

from sqlalchemy import case, func, or_, select

from app.core.errors import BizError, ErrorCode
from app.modules.campaign.models import Campaign, CampaignStat, CampaignTarget
from app.modules.org.models import EmpDept, EmpUser
from app.modules.report.models import MailReport
from app.modules.template.models import EmailTemplate
from app.modules.tracking.models import TrackEvent

from .models import OpenApp

_SENT_STATUS = ("sent", "delivered")
_VICTIM = or_(CampaignTarget.submit_flag == 1, CampaignTarget.attach_run_count > 0)
_TRACK_TYPES = ("open", "click", "submit", "attach_run")


def _dt(v: datetime | None) -> str | None:
    return v.strftime("%Y-%m-%d %H:%M:%S") if v else None


def _pct(n, d) -> float:
    return round(n / d * 100, 1) if d else 0.0


def _window_days(range_: str) -> int:
    return {"7d": 7, "month": 30, "quarter": 90}.get(range_, 30)


def _get_campaign_or_404(db, cid: int) -> Campaign:
    c = db.get(Campaign, cid)
    if c is None:
        raise BizError(ErrorCode.NOT_FOUND, "演练不存在")
    return c


def _stat_of(db, cid: int) -> dict:
    stat = db.get(CampaignStat, cid)
    return {
        "delivered": int(stat.delivered_cnt or 0) if stat else 0,
        "open": int(stat.open_cnt or 0) if stat else 0,
        "click": int(stat.click_cnt or 0) if stat else 0,
        "submit": int(stat.submit_cnt or 0) if stat else 0,
        "attach": int(stat.attach_cnt or 0) if stat else 0,
        "report": int(stat.report_cnt or 0) if stat else 0,
    }


# ---------- campaign ----------


def list_campaigns(db, *, page=1, page_size=20, status: str | None = None) -> dict:
    stmt = select(Campaign)
    if status:
        stmt = stmt.where(Campaign.status == status)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(Campaign.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    stats = {cid: _stat_of(db, cid) for cid in [c.id for c in rows]}
    return {
        "total": total, "page": page, "page_size": page_size,
        "list": [{
            "id": c.id, "name": c.name, "type": c.type, "status": c.status,
            "target_count": c.target_count,
            "schedule_type": c.schedule_type, "schedule_at": _dt(c.schedule_at),
            "started_at": _dt(c.started_at), "ended_at": _dt(c.ended_at),
            "created_at": _dt(c.created_at), "stats": stats.get(c.id),
        } for c in rows],
    }


def get_campaign(db, cid: int) -> dict:
    c = _get_campaign_or_404(db, cid)
    s = _stat_of(db, cid)
    victim = s["submit"] + s["attach"]
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "type": c.type, "status": c.status,
        "target_count": c.target_count,
        "schedule_type": c.schedule_type, "schedule_at": _dt(c.schedule_at),
        "batch_count": c.batch_count, "batch_interval_min": c.batch_interval_min,
        "training_policy": c.training_policy,
        "started_at": _dt(c.started_at), "ended_at": _dt(c.ended_at),
        "created_at": _dt(c.created_at),
        "stats": s,
        "victim_count": victim,
        "victim_rate": _pct(victim, c.target_count or 0),
    }


def create_campaign(db, app: OpenApp, payload) -> int:
    """创建演练：红线 4 强制授权确认（schema 必填 + service 二次校验）。

    产物始终为草稿（schedule_type=now → draft；timed → scheduled），
    启动发送仅在平台内人工操作——API 不提供启动动作。
    """
    if not payload.auth_confirmed:
        raise BizError(ErrorCode.PARAM_INVALID, "auth_confirmed 必须为 true（授权确认）")
    from types import SimpleNamespace

    from app.modules.campaign import service as campaign_svc

    creator = SimpleNamespace(
        id=app.created_by or 0,
        real_name=f"开放平台应用:{app.name}",
        username=f"app:{app.app_id}",
    )
    return campaign_svc.create_campaign(db, creator, payload)


def list_targets(db, cid: int, *, page=1, page_size=20,
                 victim_only: bool = False) -> dict:
    _get_campaign_or_404(db, cid)
    stmt = (
        select(CampaignTarget, EmpUser.name, EmpUser.email, EmpDept.name)
        .join(EmpUser, EmpUser.id == CampaignTarget.user_id)
        .join(EmpDept, EmpDept.id == EmpUser.dept_id, isouter=True)
        .where(CampaignTarget.campaign_id == cid)
    )
    if victim_only:
        stmt = stmt.where(_VICTIM)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.execute(
        stmt.order_by(CampaignTarget.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "list": [{
            "id": t.id, "user_id": t.user_id, "name": name, "email": email,
            "dept": dept_name, "send_status": t.send_status,
            "sent_at": _dt(t.sent_at),
            "open_count": t.open_count, "click_count": t.click_count,
            "submit_flag": bool(t.submit_flag), "submit_at": _dt(t.submit_at),
            "attach_run_count": t.attach_run_count,
            "report_flag": bool(t.report_flag),
            "victim": bool(t.submit_flag) or bool(t.attach_run_count),
        } for t, name, email, dept_name in rows],
    }


def campaign_report(db, cid: int) -> dict:
    """演练结果报表：指标卡 + 漏斗 + 中招明细 TOP + 近 14 天行为趋势。

    与内部报表同口径：中招 = 提交 + 附件运行；漏斗逐级转换率在上一级为 0
    而本级有值时置 None（数据缺失不伪造 0%），转换率钳位 100%。
    """
    c = _get_campaign_or_404(db, cid)
    target = int(c.target_count or 0)
    s = _stat_of(db, cid)
    victim = s["submit"] + s["attach"]
    open_cnt, click_cnt = s["open"], s["click"]
    victim_rate = _pct(victim, target)

    def _rate(cur, prev):
        if prev <= 0:
            return None if cur > 0 else 0.0
        return round(min(100.0, cur / prev * 100), 1)

    # 中招明细 TOP 20（含附件运行：高危行为与提交合并口径）
    victims = db.execute(
        select(EmpUser.name, EmpUser.email, EmpDept.name,
               CampaignTarget.submit_flag, CampaignTarget.attach_run_count,
               CampaignTarget.click_count, CampaignTarget.open_count)
        .join(EmpUser, EmpUser.id == CampaignTarget.user_id)
        .join(EmpDept, EmpDept.id == EmpUser.dept_id, isouter=True)
        .where(CampaignTarget.campaign_id == cid, _VICTIM)
        .order_by(CampaignTarget.submit_at.desc().nulls_last(),
                  CampaignTarget.attach_run_count.desc())
        .limit(20)
    ).all()

    # 近 14 天行为事件（按天聚合 open/click/submit/attach_run）
    since = datetime.now() - timedelta(days=13)
    day_rows = db.execute(
        select(func.date(TrackEvent.created_at).label("d"),
               TrackEvent.event_type, func.count())
        .where(TrackEvent.campaign_id == cid,
               TrackEvent.created_at >= since,
               TrackEvent.event_type.in_(_TRACK_TYPES))
        .group_by(func.date(TrackEvent.created_at), TrackEvent.event_type)
    ).all()
    day_map: dict[str, dict] = {}
    for d, etype, cnt in day_rows:
        day_map.setdefault(str(d), {})[etype] = int(cnt)

    return {
        "campaign": {"id": c.id, "name": c.name, "status": c.status},
        "metrics": [
            {"title": "发送数", "value": target},
            {"title": "打开数", "value": open_cnt, "rate": _pct(open_cnt, target)},
            {"title": "点击数", "value": click_cnt, "rate": _pct(click_cnt, target)},
            {"title": "中招数", "value": victim, "rate": victim_rate},
            {"title": "举报数", "value": s["report"], "rate": _pct(s["report"], target)},
            {"title": "综合得分", "value": round(max(0.0, 100 - victim_rate * 2))},
        ],
        "funnel": [
            {"stage": "发送", "count": target},
            {"stage": "打开", "count": open_cnt, "rate": _rate(open_cnt, target)},
            {"stage": "点击", "count": click_cnt, "rate": _rate(click_cnt, open_cnt)},
            {"stage": "中招", "count": victim, "rate": _rate(victim, click_cnt)},
        ],
        "victims_top": [{
            "name": r[0], "email": r[1], "dept": r[2],
            "submit": bool(r[3]), "attach_run": int(r[4]),
            "click_count": int(r[5]), "open_count": int(r[6]),
        } for r in victims],
        "daily": {
            "labels": sorted(day_map.keys()),
            "open": [day_map[d].get("open", 0) for d in sorted(day_map.keys())],
            "click": [day_map[d].get("click", 0) for d in sorted(day_map.keys())],
            "victim": [day_map[d].get("submit", 0) + day_map[d].get("attach_run", 0)
                       for d in sorted(day_map.keys())],
        },
    }


# ---------- report ----------


def overview(db) -> dict:
    c_total = int(db.scalar(select(func.count()).select_from(Campaign)) or 0)
    running = int(db.scalar(
        select(func.count()).select_from(Campaign)
        .where(Campaign.status.in_(("sending", "running", "paused")))
    ) or 0)
    emp_total = int(db.scalar(
        select(func.count()).select_from(EmpUser).where(EmpUser.status == 1)
    ) or 0)
    dept_total = int(db.scalar(select(func.count()).select_from(EmpDept)) or 0)
    victim_total = int(db.scalar(
        select(func.count()).select_from(CampaignTarget).where(_VICTIM)
    ) or 0)
    report_total = int(db.scalar(select(func.count()).select_from(MailReport)) or 0)
    last_at = db.scalar(select(func.max(Campaign.started_at)))
    return {
        "campaign_total": c_total, "campaign_running": running,
        "emp_total": emp_total, "dept_total": dept_total,
        "victim_total": victim_total, "report_total": report_total,
        "last_campaign_at": _dt(last_at),
    }


def trend(db, range_: str = "month") -> dict:
    """中招趋势：按天聚合行为事件（victim = submit + attach_run 事件数）。"""
    since = datetime.now() - timedelta(days=_window_days(range_))
    rows = db.execute(
        select(func.date(TrackEvent.created_at).label("d"),
               TrackEvent.event_type, func.count())
        .where(TrackEvent.created_at >= since,
               TrackEvent.event_type.in_(_TRACK_TYPES))
        .group_by(func.date(TrackEvent.created_at), TrackEvent.event_type)
        .order_by(func.date(TrackEvent.created_at))
    ).all()
    day_map: dict[str, dict] = {}
    for d, etype, cnt in rows:
        day_map.setdefault(str(d), {})[etype] = int(cnt)
    labels = sorted(day_map.keys())
    return {
        "labels": labels,
        "open": [day_map[d].get("open", 0) for d in labels],
        "click": [day_map[d].get("click", 0) for d in labels],
        "victim": [day_map[d].get("submit", 0) + day_map[d].get("attach_run", 0)
                   for d in labels],
    }


def department_report(db, range_: str = "month") -> dict:
    """部门横向对比（campaign_target 直查，投递时间窗口，中招=提交+附件运行）。"""
    since = datetime.now() - timedelta(days=_window_days(range_))
    submit_c = func.sum(case((_VICTIM, 1), else_=0))
    stmt = (
        select(
            EmpUser.dept_id,
            func.sum(case((CampaignTarget.send_status.in_(_SENT_STATUS), 1), else_=0)),
            func.sum(case((CampaignTarget.first_open_at.is_not(None), 1), else_=0)),
            func.sum(case((CampaignTarget.first_click_at.is_not(None), 1), else_=0)),
            submit_c,
            func.sum(case((CampaignTarget.report_flag == 1, 1), else_=0)),
            EmpDept.name,
        )
        .join(EmpUser, EmpUser.id == CampaignTarget.user_id)
        .join(EmpDept, EmpDept.id == EmpUser.dept_id, isouter=True)
        .group_by(EmpUser.dept_id, EmpDept.name)
        .order_by(submit_c.desc())
    )
    rows = db.execute(stmt.where(CampaignTarget.sent_at >= since)).all()
    if not rows:  # 窗口内无投递回退全量（与内部报表一致）
        rows = db.execute(stmt).all()
    total_map = dict(db.execute(
        select(EmpUser.dept_id, func.count(EmpUser.id))
        .where(EmpUser.status == 1).group_by(EmpUser.dept_id)
    ).all())
    out = []
    for dept_id, target, open_cnt, click_cnt, submit_cnt, report_cnt, name in rows:
        target = float(target or 0)
        label = name or f"部门{dept_id or ''}"
        out.append({
            "dept": label,
            "targetCount": int(target),
            "victim": int(submit_cnt or 0),
            "report": int(report_cnt or 0),
            "total": int(total_map.get(dept_id, 0) or 0),
            "openRate": _pct(open_cnt or 0, target),
            "clickRate": _pct(click_cnt or 0, target),
            "submitRate": _pct(submit_cnt or 0, target),
            "reportRate": _pct(report_cnt or 0, target),
        })
    return {"rows": out}


# ---------- user ----------


def _user_behavior(db, user_ids: list[int]) -> dict[int, dict]:
    if not user_ids:
        return {}
    camp = db.execute(
        select(CampaignTarget.user_id,
               func.count(func.distinct(CampaignTarget.campaign_id)),
               func.sum(case((_VICTIM, 1), else_=0)))
        .where(CampaignTarget.user_id.in_(user_ids))
        .group_by(CampaignTarget.user_id)
    ).all()
    evt = db.execute(
        select(TrackEvent.user_id,
               func.sum(case((TrackEvent.event_type == "open", 1), else_=0)),
               func.sum(case((TrackEvent.event_type == "click", 1), else_=0)))
        .where(TrackEvent.user_id.in_(user_ids))
        .group_by(TrackEvent.user_id)
    ).all()
    out = {uid: {"campaigns": 0, "victim": 0, "open": 0, "click": 0} for uid in user_ids}
    for uid, camps, victim in camp:
        out.setdefault(uid, {"campaigns": 0, "victim": 0, "open": 0, "click": 0})
        out[uid]["campaigns"] = int(camps or 0)
        out[uid]["victim"] = int(victim or 0)
    for uid, open_n, click_n in evt:
        out.setdefault(uid, {"campaigns": 0, "victim": 0, "open": 0, "click": 0})
        out[uid]["open"] = int(open_n or 0)
        out[uid]["click"] = int(click_n or 0)
    return out


def list_users(db, *, page=1, page_size=20, kw: str | None = None,
               dept_id: int | None = None) -> dict:
    stmt = select(EmpUser, EmpDept.name).join(EmpDept, EmpDept.id == EmpUser.dept_id, isouter=True)
    if kw:
        like = f"%{kw.lower()}%"
        stmt = stmt.where(or_(func.lower(EmpUser.name).like(like),
                              func.lower(EmpUser.email).like(like)))
    if dept_id:
        stmt = stmt.where(EmpUser.dept_id == dept_id)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.execute(
        stmt.order_by(EmpUser.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    behavior = _user_behavior(db, [u.id for u, _ in rows])
    return {
        "total": total, "page": page, "page_size": page_size,
        "list": [{
            "id": u.id, "emp_no": u.emp_no, "name": u.name, "email": u.email,
            "dept": dept_name, "position": u.position,
            "status": "active" if u.status == 1 else "inactive",
            "behavior": behavior.get(u.id),
        } for u, dept_name in rows],
    }


def get_user(db, uid: int) -> dict:
    u = db.get(EmpUser, uid)
    if u is None:
        raise BizError(ErrorCode.NOT_FOUND, "员工不存在")
    dept = db.get(EmpDept, u.dept_id)
    behavior = _user_behavior(db, [uid]).get(uid, {})
    recent = db.execute(
        select(TrackEvent.event_type, TrackEvent.created_at)
        .where(TrackEvent.user_id == uid)
        .order_by(TrackEvent.id.desc()).limit(10)
    ).all()
    return {
        "id": u.id, "emp_no": u.emp_no, "name": u.name, "email": u.email,
        "dept": dept.name if dept else None, "position": u.position,
        "status": "active" if u.status == 1 else "inactive",
        "behavior": behavior,
        "recent_events": [{"event_type": e, "created_at": _dt(ts)} for e, ts in recent],
    }


# ---------- template / mail_report / system ----------


def list_templates(db, scene: str | None = None) -> dict:
    stmt = select(EmailTemplate)
    if scene:
        stmt = stmt.where(EmailTemplate.scene == scene)
    rows = db.scalars(stmt.order_by(EmailTemplate.id.desc())).all()
    return {"total": len(rows), "list": [{
        "id": t.id, "name": t.name, "scene": t.scene, "subject": t.subject,
        "source": t.source, "status": t.status, "stars": t.stars,
        "used_count": t.used_count, "click_rate": float(t.click_rate or 0),
        "created_at": _dt(t.created_at),
    } for t in rows]}


def get_template(db, tid: int) -> dict:
    t = db.get(EmailTemplate, tid)
    if t is None:
        raise BizError(ErrorCode.NOT_FOUND, "模板不存在")
    return {
        "id": t.id, "name": t.name, "scene": t.scene, "subject": t.subject,
        "html_body": t.html_body, "variables": t.variables or [],
        "source": t.source, "status": t.status, "stars": t.stars,
        "track_pixel": bool(t.track_pixel), "track_link": bool(t.track_link),
        "track_attach": bool(t.track_attach),
        "created_at": _dt(t.created_at),
    }


def list_mail_reports(db, *, page=1, page_size=20,
                      classification: str | None = None) -> dict:
    stmt = select(MailReport)
    if classification:
        stmt = stmt.where(MailReport.classification == classification)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(MailReport.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "list": [{
            "id": r.id, "channel": r.channel, "subject": r.subject,
            "from_addr": r.from_addr, "reporter_email": r.reporter_email,
            "classification": r.classification, "classifier": r.classifier,
            "matched_campaign_id": r.matched_campaign_id,
            "created_at": _dt(r.created_at), "handled_at": _dt(r.handled_at),
        } for r in rows],
    }


def system_info(db) -> dict:
    from app.core.config import settings

    return {
        "app_name": settings.app_name,
        "campaign_total": int(db.scalar(select(func.count()).select_from(Campaign)) or 0),
        "emp_total": int(db.scalar(select(func.count()).select_from(EmpUser)) or 0),
        "dept_total": int(db.scalar(select(func.count()).select_from(EmpDept)) or 0),
    }
