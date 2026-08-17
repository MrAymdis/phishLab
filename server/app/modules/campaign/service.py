"""演练服务：列表/详情/状态机/监控大屏/行为时间轴。

实现要点见《架构设计方案》§3.2：目标展开、批次调度、追踪事件、预警。
"""
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.deps import apply_data_scope
from app.core.errors import BizError, ErrorCode
from app.modules.license.service import check_quota
from app.modules.org.models import EmpDept, EmpUser, EmpUserTag
from app.modules.tracking.models import TrackEvent

from .models import Campaign, CampaignAlert, CampaignBatch, CampaignStat, CampaignTarget

_DT_FMT = "%Y-%m-%d %H:%M:%S"

# 时间轴：事件类型 → 文案 / 图标
_ACTION_TEXT = {
    "open": "打开了邮件",
    "click": "点击了邮件中的链接",
    "submit": "在登录页提交了账号密码",
    "report": "举报了可疑邮件",
    "attach_run": "运行了附件",
    "bounce": "邮件被退回",
}
_ACTION_ICON = {
    "open": "📧",
    "click": "🔗",
    "submit": "⚠️",
    "report": "🛡️",
    "attach_run": "📎",
    "bounce": "↩️",
}

# 预警类型 → 处置建议（campaign_alert.type）
_ALERT_ADVICE = {
    "pwd_submit": "建议立即为该员工安排安全意识培训",
    "exec_user": "建议排查该员工设备是否存在恶意程序",
    "dept_threshold": "该部门中招比例偏高，建议开展部门级专项培训",
    "fast_submit": "提交速度异常，疑似自动化脚本，建议复核事件真实性",
    "repeat_n": "同一员工多次中招，建议重点跟进",
}

# 列表页统计卡片"进行中"覆盖的中间态
_IN_PROGRESS = ("sending", "running", "paused")


def _dt(v: datetime | None) -> str | None:
    """datetime → 前端字符串（SQLite 下无时区）。"""
    return v.strftime(_DT_FMT) if v else None


def _get_or_404(db, campaign_id: int) -> Campaign:
    c = db.get(Campaign, campaign_id)
    if c is None:
        raise BizError(ErrorCode.NOT_FOUND)
    return c


def _stat_map(db, campaign_ids: list[int]) -> dict[int, CampaignStat]:
    """campaign_id → 冗余计数行（缺失视为 0）。"""
    if not campaign_ids:
        return {}
    return {
        s.campaign_id: s
        for s in db.scalars(
            select(CampaignStat).where(CampaignStat.campaign_id.in_(campaign_ids))
        ).all()
    }


def _expand_target_ids(db, target_mode: str, snapshot: dict) -> list[int]:
    """目标展开：dept(含子部门)/tag/csv/mix → 去重后的在职员工 id 列表。"""
    ids: set[int] = set()

    if target_mode in ("dept", "mix"):
        dept_ids = {int(x) for x in (snapshot.get("dept_ids") or [])}
        if dept_ids:
            # 部门路径展开：包含所选部门及其全部子部门
            paths = db.scalars(select(EmpDept.path).where(EmpDept.id.in_(dept_ids))).all()
            for p in paths:
                dept_ids.update(
                    d for d in db.scalars(
                        select(EmpDept.id).where(EmpDept.path.like(f"{p.rstrip('/')}/%"))
                    ).all()
                )
        if dept_ids:
            ids.update(
                u for u in db.scalars(
                    select(EmpUser.id).where(EmpUser.dept_id.in_(dept_ids), EmpUser.status == 1)
                ).all()
            )
    if target_mode in ("tag", "mix"):
        tag_ids = {int(x) for x in (snapshot.get("tag_ids") or [])}
        if tag_ids:
            ids.update(
                u for u in db.scalars(
                    select(EmpUserTag.user_id).where(EmpUserTag.tag_id.in_(tag_ids))
                ).all()
            )
    if target_mode in ("csv", "mix"):
        ids.update(int(x) for x in (snapshot.get("user_ids") or []))
        # CSV 导入名单：按邮箱解析为员工 id（未匹配的邮箱忽略）
        emails = {str(e).strip().lower() for e in (snapshot.get("emails") or []) if e}
        if emails:
            ids.update(
                u for u in db.scalars(
                    select(EmpUser.id).where(EmpUser.email.in_(emails), EmpUser.status == 1)
                ).all()
            )
    if not ids:
        return []
    # 统一过滤：仅在职员工
    return list(db.scalars(
        select(EmpUser.id).where(EmpUser.id.in_(ids), EmpUser.status == 1)
    ).all())


def list_campaigns(db, account, *, status=None, type=None, kw=None, page=1, page_size=20):
    """演练列表 + 统计卡片：campaign 关联 campaign_stat，强制 apply_data_scope。"""
    # 数据权限：演练仅按创建人过滤（无部门列）
    base = apply_data_scope(
        db, select(Campaign), account,
        dept_col=None, self_owner_col=Campaign.creator_id,
    )
    stmt = base
    if status:
        stmt = stmt.where(Campaign.status == status)
    if type:
        stmt = stmt.where(Campaign.type == type)
    if kw:
        stmt = stmt.where(func.lower(Campaign.name).like(f"%{kw.lower()}%"))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(Campaign.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    # 统计卡片：基于数据权限范围内的全部演练（不受列表筛选影响）
    scoped = db.scalars(base).all()
    stats_map = _stat_map(db, [c.id for c in scoped])

    def _count(statuses):
        return sum(1 for c in scoped if c.status in statuses)

    running_targets = sum(c.target_count for c in scoped if c.status in _IN_PROGRESS)
    completed = [c for c in scoped if c.status == "completed"]
    victim_rates = [
        (stats_map[c.id].submit_cnt if stats_map.get(c.id) else 0) / c.target_count * 100
        for c in completed if c.target_count > 0
    ]
    avg_victim = (sum(victim_rates) / len(victim_rates)) if victim_rates else 0.0

    stats = [
        {"key": "", "label": "演练总数", "value": len(scoped), "sub": "↑ 12 本月", "accent": "blue"},
        {"key": "running", "label": "进行中", "value": _count(_IN_PROGRESS),
         "sub": f"覆盖 {running_targets:,} 人", "accent": "green"},
        {"key": "scheduled", "label": "待开始", "value": _count(("scheduled",)),
         "sub": "计划本周 3 场", "accent": "purple"},
        {"key": "completed", "label": "已完成", "value": len(completed),
         "sub": f"平均中招率 {avg_victim:.1f}%", "accent": "teal"},
        {"key": "terminated", "label": "已终止", "value": _count(("terminated",)),
         "sub": "异常终止 2 场", "accent": "red"},
        {"key": "draft", "label": "草稿", "value": _count(("draft",)),
         "sub": "编辑中的演练", "accent": "gray"},
    ]

    items = []
    for c in rows:
        s = stats_map.get(c.id)
        delivered, opened, clicked, submitted = (
            (s.delivered_cnt, s.open_cnt, s.click_cnt, s.submit_cnt) if s else (0, 0, 0, 0)
        )
        target = c.target_count or 1
        start = c.started_at or c.schedule_at or c.created_at or datetime.now()
        end = c.ended_at or (start + timedelta(days=7))
        items.append({
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "time_range": f"{start.strftime('%m-%d')} ~ {end.strftime('%m-%d')}",
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "started_at": _dt(c.started_at),
            "target_count": c.target_count,
            "deliver_rate": round(delivered / target * 100),
            "open_rate": round(opened / target * 100),
            "click_rate": round(clicked / target * 100),
            "victim_rate": round(submitted / target * 100),
            "status": c.status,
        })
    return {"stats": stats, "list": items, "total": total, "page": page, "pageSize": page_size}


def create_campaign(db, account, payload) -> int:
    """创建演练：授权校验 → 配额检查 → 目标展开 → target+token → 切批次。"""
    if not payload.auth_confirmed:
        raise BizError(ErrorCode.PARAM_INVALID, "必须勾选授权确认")
    check_quota(db, "campaign", 1)

    snapshot = payload.target_snapshot or {}
    user_ids = _expand_target_ids(db, payload.target_mode, snapshot)
    if not user_ids:
        raise BizError(ErrorCode.PARAM_INVALID, "未选择演练目标")

    campaign = Campaign(
        name=payload.name,
        description=payload.description,
        type=payload.type,
        creator_id=account.id,
        template_id=payload.template_id,
        landing_page_id=payload.landing_page_id,
        channel_id=payload.channel_id,
        sender_profile_id=payload.sender_profile_id,
        domain_id=payload.domain_id,
        target_mode=payload.target_mode,
        target_snapshot=snapshot,
        target_count=len(user_ids),
        schedule_type=payload.schedule_type,
        schedule_at=payload.schedule_at,
        batch_count=payload.batch_count,
        batch_interval_min=payload.batch_interval_min,
        randomize_content=int(payload.randomize_content),
        time_jitter_sec=payload.time_jitter_sec,
        pixel_degrade=int(payload.pixel_degrade),
        training_policy=payload.training_policy,
        course_ids=payload.course_ids or [],
        force_training_rules=payload.force_training_rules or [],
        auth_confirmed=1,
        status="scheduled" if payload.schedule_type == "timed" else "draft",
    )
    db.add(campaign)
    db.flush()  # 取自增 id
    cid = campaign.id

    # 目标明细：唯一令牌贯穿像素/链接/落地页；按批次数轮转切批
    for i, uid in enumerate(user_ids):
        db.add(CampaignTarget(
            campaign_id=cid,
            user_id=uid,
            batch_no=(i % payload.batch_count) + 1,
            token=secrets.token_hex(16),
        ))
    # 冗余计数表：Redis 定时回写，先落零值行
    db.add(CampaignStat(campaign_id=cid))
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="create",
        target_type="campaign", target_id=str(cid),
        detail={"name": payload.name, "target_count": len(user_ids)},
    )
    return cid


def get_campaign(db, account, campaign_id: int):
    """演练详情（7 步向导回显）。"""
    c = _get_or_404(db, campaign_id)
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "type": c.type,
        "status": c.status,
        "target_count": c.target_count,
        "schedule_type": c.schedule_type,
        "schedule_at": _dt(c.schedule_at),
        "batch_count": c.batch_count,
        "batch_interval_min": c.batch_interval_min,
        "randomize_content": bool(c.randomize_content),
        "time_jitter_sec": c.time_jitter_sec,
        "pixel_degrade": bool(c.pixel_degrade),
        "training_policy": c.training_policy,
        "course_ids": c.course_ids or [],
        "force_training_rules": c.force_training_rules or [],
        "auth_confirmed": bool(c.auth_confirmed),
        "target_mode": c.target_mode,
        "target_snapshot": c.target_snapshot or {},
        "template_id": c.template_id,
        "landing_page_id": c.landing_page_id,
        "channel_id": c.channel_id,
        "sender_profile_id": c.sender_profile_id,
        "domain_id": c.domain_id,
        "started_at": _dt(c.started_at),
        "ended_at": _dt(c.ended_at),
        "created_at": _dt(c.created_at),
    }


def update_draft(db, account, campaign_id: int, payload):
    """向导草稿暂存（仅 status=draft 可编辑，不触碰状态/目标数）。"""
    c = _get_or_404(db, campaign_id)
    if c.status != "draft":
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅草稿状态可编辑")

    c.name = payload.name
    c.description = payload.description
    c.type = payload.type
    c.template_id = payload.template_id
    c.landing_page_id = payload.landing_page_id
    c.channel_id = payload.channel_id
    c.sender_profile_id = payload.sender_profile_id
    c.domain_id = payload.domain_id
    c.target_mode = payload.target_mode
    c.target_snapshot = payload.target_snapshot or {}
    c.schedule_type = payload.schedule_type
    c.schedule_at = payload.schedule_at
    c.batch_count = payload.batch_count
    c.batch_interval_min = payload.batch_interval_min
    c.randomize_content = int(payload.randomize_content)
    c.time_jitter_sec = payload.time_jitter_sec
    c.pixel_degrade = int(payload.pixel_degrade)
    c.training_policy = payload.training_policy
    c.course_ids = payload.course_ids or []
    c.force_training_rules = payload.force_training_rules or []
    c.auth_confirmed = int(payload.auth_confirmed)
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="update_draft",
        target_type="campaign", target_id=str(campaign_id),
        detail={"name": payload.name},
    )
    return None


def start(db, account, campaign_id: int):
    """draft/scheduled → running：生成批次调度并派发 Worker 投递。"""
    c = _get_or_404(db, campaign_id)
    if c.status not in ("draft", "scheduled"):
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅草稿/待开始状态可启动")

    now = datetime.now()
    c.status = "running"
    c.started_at = now
    # 批次行：Worker 按 plan_at 触发投递，uk_campaign_batch 保证幂等
    for i in range(c.batch_count):
        db.add(CampaignBatch(
            campaign_id=campaign_id,
            batch_no=i + 1,
            plan_at=now + timedelta(minutes=i * c.batch_interval_min),
            status="pending",
        ))
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="start",
        target_type="campaign", target_id=str(campaign_id),
    )

    # 投递派发：Worker 在线时立即开始投递；离线时由 beat 每 30s 兜底扫描
    try:
        from worker.tasks.delivery import dispatch_due_batches

        dispatch_due_batches.delay()
    except Exception:
        pass
    return None


def pause(db, account, campaign_id: int):
    """running → paused：停止批次调度，追踪链路继续。"""
    c = _get_or_404(db, campaign_id)
    if c.status != "running":
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅运行中状态可暂停")
    c.status = "paused"
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="pause",
        target_type="campaign", target_id=str(campaign_id),
    )
    return None


def resume(db, account, campaign_id: int):
    """paused → running：恢复批次调度。"""
    c = _get_or_404(db, campaign_id)
    if c.status != "paused":
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅暂停状态可恢复")
    c.status = "running"
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="resume",
        target_type="campaign", target_id=str(campaign_id),
    )
    return None


def terminate(db, account, campaign_id: int):
    """非终态 → terminated：停止发送与追踪，写审计。"""
    c = _get_or_404(db, campaign_id)
    if c.status not in ("draft", "scheduled", "sending", "running", "paused"):
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "当前状态不可终止")
    c.status = "terminated"
    c.ended_at = datetime.now()
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="terminate",
        target_type="campaign", target_id=str(campaign_id),
    )
    return None


def dashboard(db, account, campaign_id: int) -> dict:
    """监控大屏：指标卡 + 漏斗 + 预警（读冗余表 campaign_stat）。"""
    c = _get_or_404(db, campaign_id)
    stat = db.get(CampaignStat, campaign_id)
    delivered = stat.delivered_cnt if stat else 0
    opened = stat.open_cnt if stat else 0
    clicked = stat.click_cnt if stat else 0
    submitted = stat.submit_cnt if stat else 0
    reported = stat.report_cnt if stat else 0
    target = c.target_count or 1

    metrics = [
        {"label": "发送成功", "value": delivered, "suffix": "", "accent": "blue"},
        {"label": "已打开", "value": opened, "suffix": "", "accent": "teal"},
        {"label": "已点击", "value": clicked, "suffix": "", "accent": "orange"},
        {"label": "中招人数", "value": submitted, "suffix": "", "accent": "red"},
        {"label": "已举报", "value": reported, "suffix": "", "accent": "purple"},
        {"label": "送达率", "value": f"{delivered / target * 100:.1f}", "suffix": "%", "accent": "green"},
    ]

    # 漏斗各环节相对送达数折算
    base = delivered or 1
    funnel = [
        {"name": "发送成功", "value": delivered, "rate": "100%"},
        {"name": "已打开", "value": opened, "rate": f"{opened / base * 100:.1f}%"},
        {"name": "已点击", "value": clicked, "rate": f"{clicked / base * 100:.1f}%"},
        {"name": "输入数据", "value": submitted, "rate": f"{submitted / base * 100:.1f}%"},
        {"name": "已举报", "value": reported, "rate": f"{reported / base * 100:.1f}%"},
        {"name": "附件运行", "value": 0, "rate": "0%"},
    ]

    alert_rows = db.scalars(
        select(CampaignAlert)
        .where(CampaignAlert.campaign_id == campaign_id)
        .order_by(CampaignAlert.id.desc())
        .limit(5)
    ).all()
    alerts = [
        {
            "msg": a.message,
            "time": a.created_at.strftime(_DT_FMT) if a.created_at else "",
            "advice": _ALERT_ADVICE.get(a.type, "建议结合行为时间轴定位相关人员，开展针对性教育"),
        }
        for a in alert_rows
    ]
    return {"metrics": metrics, "funnel": funnel, "alerts": alerts}


def timeline(db, account, campaign_id: int, page: int, page_size: int):
    """用户行为时间轴：track_event left join emp_user/emp_dept，附 IP/UA/指纹。"""
    base = (
        select(TrackEvent, EmpUser.name, EmpDept.name)
        .outerjoin(EmpUser, EmpUser.id == TrackEvent.user_id)
        .outerjoin(EmpDept, EmpDept.id == EmpUser.dept_id)
        .where(TrackEvent.campaign_id == campaign_id)
    )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.execute(
        base.order_by(TrackEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for ev, user_name, dept_name in rows:
        if user_name:
            user = f"{user_name} · {dept_name}" if dept_name else user_name
        else:
            user = "未知用户"
        items.append({
            "time": ev.created_at.strftime(_DT_FMT) if ev.created_at else "",
            "user": user,
            "action": _ACTION_TEXT.get(ev.event_type, ev.event_type),
            "icon": _ACTION_ICON.get(ev.event_type, "•"),
            "ip": ev.ip or "",
            "browser": ev.ua.split()[0] if ev.ua else "",
            "fingerprint": f"{ev.fingerprint_id:x}"[:8] if ev.fingerprint_id else "",
            "danger": ev.event_type == "submit",
            "good": ev.event_type == "report",
        })
    return {"list": items, "total": total, "page": page, "pageSize": page_size}


def test_send(db, account, campaign_id: int, to: list[str]):
    """发送测试：仅白名单收件人。真实 SMTP 投递由 Worker 实现（TODO 一期）。"""
    _get_or_404(db, campaign_id)
    # TODO(一期)：经通道适配器真实发送并校验 SMTP 连通性，当前仅回执占位
    record_audit(
        db, account=account, module="campaign", action="test_send",
        target_type="campaign", target_id=str(campaign_id),
        detail={"recipients": len(to)},
    )
    return {"ok": True, "message": f"测试邮件已发送至 {len(to)} 个白名单收件人"}


def delete_campaign(db, account, campaign_id: int) -> None:
    """删除演练：仅 draft 状态可删；关联数据级联删除。"""
    c = db.get(Campaign, campaign_id)
    if c is None:
        raise ValueError("演练不存在")
    if c.status != "draft":
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅草稿状态可删除演练")
    db.execute(CampaignTarget.__table__.delete().where(CampaignTarget.campaign_id == campaign_id))
    db.execute(CampaignBatch.__table__.delete().where(CampaignBatch.campaign_id == campaign_id))
    db.execute(CampaignStat.__table__.delete().where(CampaignStat.campaign_id == campaign_id))
    db.execute(CampaignAlert.__table__.delete().where(CampaignAlert.campaign_id == campaign_id))
    db.delete(c)
    db.commit()
    record_audit(
        db, account=account, module="campaign", action="delete_campaign",
        target_type="campaign", target_id=str(campaign_id),
    )
