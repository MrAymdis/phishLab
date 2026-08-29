"""演练服务：列表/详情/状态机/监控大屏/行为时间轴。

实现要点见《架构设计方案》§3.2：目标展开、批次调度、追踪事件、预警。
"""
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update

from app.core.audit import record_audit

logger = logging.getLogger("phishlab.campaign")
from app.core.deps import apply_data_scope, get_scoped_or_404
from app.core.errors import BizError, ErrorCode
from app.modules.license.service import check_quota
from app.modules.org.models import EmpDept, EmpUser, EmpUserTag
from app.modules.tracking.models import TrackEvent

from .models import Campaign, CampaignAlert, CampaignAttachment, CampaignBatch, CampaignStat, CampaignTarget

_DT_FMT = "%Y-%m-%d %H:%M:%S"

# 时间轴：事件类型 → 文案 / 图标
_ACTION_TEXT = {
    "open": "打开了邮件",
    "click": "点击了邮件中的链接",
    "submit": "在登录页提交了敏感数据",
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
    "attach_run": "建议立即安排安全培训，并排查该员工设备是否感染恶意程序",
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


def _get_or_404(db, account, campaign_id: int) -> Campaign:
    """按 ID 读取演练并强制数据权限过滤（与列表同口径：按创建人归属）。"""
    return get_scoped_or_404(db, account, Campaign, campaign_id,
                             self_owner_col=Campaign.creator_id)


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


# ---------- 企业微信（social）演练 ----------

# 授权勾选项快照键（红线4）。P0 强制前 3 项；OAuth 静默身份识别披露随 P1 溯源上线后强制
_WECOM_AUTH_REQUIRED = ("wecom:written_auth", "wecom:domain_verified", "wecom:internal_only")
_WECOM_AUTH_LABELS = {
    "wecom:written_auth": "已获企业书面授权",
    "wecom:domain_verified": "应用可信域名已配置",
    "wecom:internal_only": "仅针对本企业成员",
    "wecom:oauth_disclosed": "已向员工披露静默身份识别（OAuth）",
}


def _require_wecom_auth(payload) -> None:
    """social 演练强制授权：快照须含全部企微专有条款（红线4，与 auth_confirmed 叠加校验）。"""
    if payload.type != "social":
        return
    missing = [k for k in _WECOM_AUTH_REQUIRED if k not in (payload.auth_snapshot or [])]
    if missing:
        labels = "、".join(_WECOM_AUTH_LABELS.get(k, k) for k in missing)
        raise BizError(ErrorCode.PARAM_INVALID, f"企业微信演练须勾选全部授权条款（缺：{labels}）")


def _validate_wecom_campaign(db, payload) -> None:
    """social 演练配置校验：授权条款 → 消息模板（须审核通过）→ 发送通道类型。"""
    from app.modules.channel.models import SendChannel
    from app.modules.template.models import WecomTemplate

    _require_wecom_auth(payload)
    if not payload.wecom_template_id:
        raise BizError(ErrorCode.PARAM_INVALID, "企业微信演练须选择企微消息模板")
    tpl = db.get(WecomTemplate, payload.wecom_template_id)
    if tpl is None:
        raise BizError(ErrorCode.NOT_FOUND, "企微消息模板不存在")
    if tpl.status != "approved":
        raise BizError(ErrorCode.PARAM_INVALID, "企微消息模板未审核通过，请先在模板管理完成审核")
    if payload.channel_id:
        ch = db.get(SendChannel, payload.channel_id)
        if ch is None or ch.type != "wecom":
            raise BizError(ErrorCode.PARAM_INVALID, "企业微信演练的发送通道须为企业微信类型")


def _resolve_wecom_targets(db, target_mode: str, snapshot: dict) -> tuple[list[int], list[EmpUser]]:
    """social 目标展开：仅保留已配置 wecom_userid 的员工；返回 (有效 id, 被跳过员工列表)。"""
    user_ids = _expand_target_ids(db, target_mode, snapshot)
    if not user_ids:
        return [], []
    with_userid = set(db.scalars(
        select(EmpUser.id).where(
            EmpUser.id.in_(user_ids),
            EmpUser.wecom_userid.isnot(None),
            EmpUser.wecom_userid != "",
        )
    ).all())
    skipped = list(db.scalars(
        select(EmpUser).where(EmpUser.id.in_(set(user_ids) - with_userid))
    ).all())
    return sorted(with_userid), skipped


def _alert_skipped_wecom(db, campaign_id: int, skipped: list[EmpUser]) -> None:
    """无 userid 被跳过员工的演练预警（目标展开告警，设计稿 §5.1）。"""
    if not skipped:
        return
    names = "、".join(u.name for u in skipped[:5]) + ("等" if len(skipped) > 5 else "")
    db.add(CampaignAlert(
        campaign_id=campaign_id, type="wecom_no_userid", level=2,
        message=f"{len(skipped)} 名目标员工未配置企业微信 userid 已跳过：{names}",
    ))


def list_campaigns(db, account, *, status=None, type=None, kw=None,
                   start_date: str | None = None, end_date: str | None = None,
                   page=1, page_size=20):
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
    # 时间范围：与列表"时间范围"列同口径（开始=started_at/schedule_at/created_at，
    # 结束=ended_at，无结束时间按开始+7天），区间有交集即命中
    if start_date and end_date:
        sel_start = datetime.strptime(start_date, "%Y-%m-%d")
        sel_end_excl = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        row_start = func.coalesce(Campaign.started_at, Campaign.schedule_at, Campaign.created_at)
        row_end = func.coalesce(Campaign.ended_at, row_start + timedelta(days=7))
        stmt = stmt.where(row_end >= sel_start, row_start < sel_end_excl)

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
        ((stats_map[c.id].submit_cnt + stats_map[c.id].attach_cnt)
         if stats_map.get(c.id) else 0) / c.target_count * 100
        for c in completed if c.target_count > 0
    ]
    avg_victim = (sum(victim_rates) / len(victim_rates)) if victim_rates else 0.0

    # 副文案真实化：本月新增 / 未来 7 天排期 / 终止覆盖人次
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_new = int(db.scalar(
        select(func.count()).select_from(base.where(Campaign.created_at >= month_start).subquery())
    ) or 0)
    week_plan = int(db.scalar(
        select(func.count()).select_from(base.where(
            Campaign.status == "scheduled",
            Campaign.schedule_at >= now,
            Campaign.schedule_at <= now + timedelta(days=7),
        ).subquery())
    ) or 0)
    terminated_targets = sum(c.target_count for c in scoped if c.status == "terminated")

    stats = [
        {"key": "", "label": "演练总数", "value": len(scoped),
         "sub": f"本月新增 {month_new} 场" if month_new else "本月暂无新增", "accent": "blue"},
        {"key": "running", "label": "进行中", "value": _count(_IN_PROGRESS),
         "sub": f"覆盖 {running_targets:,} 人", "accent": "green"},
        {"key": "scheduled", "label": "待开始", "value": _count(("scheduled",)),
         "sub": f"未来 7 天计划 {week_plan} 场" if week_plan else "暂无排期", "accent": "purple"},
        {"key": "completed", "label": "已完成", "value": len(completed),
         "sub": f"平均中招率 {avg_victim:.1f}%", "accent": "teal"},
        {"key": "terminated", "label": "已终止", "value": _count(("terminated",)),
         "sub": f"覆盖 {terminated_targets:,} 人", "accent": "red"},
        {"key": "draft", "label": "草稿", "value": _count(("draft",)),
         "sub": "编辑中的演练", "accent": "gray"},
    ]

    items = []
    for c in rows:
        s = stats_map.get(c.id)
        delivered, opened, clicked, submitted, attached = (
            (s.delivered_cnt, s.open_cnt, s.click_cnt, s.submit_cnt, s.attach_cnt)
            if s else (0, 0, 0, 0, 0)
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
            "victim_rate": round((submitted + attached) / target * 100),
            "status": c.status,
        })
    return {"stats": stats, "list": items, "total": total, "page": page, "pageSize": page_size}


def _validate_time_range(schedule_type: str, schedule_at, ended_at):
    """结束时间必须在发送开始之后（timed 按 schedule_at，now 按当前时刻）。"""
    if ended_at is None:
        return
    base = schedule_at if (schedule_type == "timed" and schedule_at) else datetime.now()
    if ended_at <= base:
        raise BizError(ErrorCode.PARAM_INVALID, "演练结束时间必须晚于发送开始时间")


def _sync_campaign_attachments(db, campaign_id: int, attachment_ids: list[int]) -> None:
    """演练↔附件载荷关联（先清后写，幂等）：载荷须存在且启用；used_count 冗余增减。"""
    from app.modules.template.models import AttachmentPayload

    old = [r[0] for r in db.execute(
        select(CampaignAttachment.payload_id)
        .where(CampaignAttachment.campaign_id == campaign_id)).all()]
    new = list(dict.fromkeys(attachment_ids or []))  # 去重保序
    if new:
        payloads = {p.id: p for p in db.scalars(
            select(AttachmentPayload).where(AttachmentPayload.id.in_(new))).all()}
        for pid in new:
            p = payloads.get(pid)
            if p is None or p.status != "enabled":
                raise BizError(ErrorCode.PARAM_INVALID, f"附件载荷 {pid} 不存在或未启用")
    db.execute(CampaignAttachment.__table__.delete()
               .where(CampaignAttachment.campaign_id == campaign_id))
    for i, pid in enumerate(new):
        db.add(CampaignAttachment(campaign_id=campaign_id, payload_id=pid,
                                  deliver_mode="inline", sort=i))
    for pid in set(old) - set(new):
        db.execute(update(AttachmentPayload).where(AttachmentPayload.id == pid)
                   .values(used_count=func.greatest(AttachmentPayload.used_count - 1, 0)))
    for pid in set(new) - set(old):
        db.execute(update(AttachmentPayload).where(AttachmentPayload.id == pid)
                   .values(used_count=AttachmentPayload.used_count + 1))


def _campaign_attachments(db, campaign_id: int) -> list[dict]:
    """演练关联附件（详情/向导回显）。"""
    from app.modules.template.models import AttachmentPayload

    rows = db.execute(
        select(CampaignAttachment, AttachmentPayload.name, AttachmentPayload.file_type)
        .join(AttachmentPayload, AttachmentPayload.id == CampaignAttachment.payload_id)
        .where(CampaignAttachment.campaign_id == campaign_id)
        .order_by(CampaignAttachment.sort, CampaignAttachment.id)
    ).all()
    return [{"id": ca.id, "payload_id": ca.payload_id, "name": name,
             "file_type": file_type, "deliver_mode": ca.deliver_mode}
            for ca, name, file_type in rows]


def _validate_base_urls(payload, request_host: str | None = None) -> tuple[str | None, str | None]:
    """演练级追踪/落地域校验：成对生效；格式/同域/协议走公共校验。返回规范化值或 (None, None)。"""
    from app.modules.settings.service import validate_base_url

    track = (payload.track_base_url or "").strip()
    landing = (payload.landing_base_url or "").strip()
    if bool(track) != bool(landing):
        raise BizError(ErrorCode.PARAM_INVALID, "追踪域与落地域需成对配置，或同时留空（沿用全局设置）")
    if not track:
        return None, None
    return (validate_base_url(track, request_host=request_host, key="track_base_url"),
            validate_base_url(landing, request_host=request_host, key="landing_base_url"))


def create_campaign(db, account, payload, request_host: str | None = None) -> int:
    """创建演练：授权校验 → 配额检查 → 目标展开 → target+token → 切批次。"""
    if not payload.auth_confirmed:
        raise BizError(ErrorCode.PARAM_INVALID, "必须勾选授权确认")
    _validate_time_range(payload.schedule_type, payload.schedule_at, payload.ended_at)
    check_quota(db, "campaign", 1)
    track_base_url, landing_base_url = _validate_base_urls(payload, request_host)

    snapshot = payload.target_snapshot or {}
    if payload.type == "social":
        _validate_wecom_campaign(db, payload)
        user_ids, skipped = _resolve_wecom_targets(db, payload.target_mode, snapshot)
    else:
        user_ids = _expand_target_ids(db, payload.target_mode, snapshot)
        skipped = []
    if not user_ids:
        if skipped:
            raise BizError(ErrorCode.PARAM_INVALID,
                           "所选目标均未配置企业微信 userid，请先在「用户和组」为员工补充 userid")
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
        track_base_url=track_base_url,
        landing_base_url=landing_base_url,
        target_mode=payload.target_mode,
        target_snapshot=snapshot,
        target_count=len(user_ids),
        schedule_type=payload.schedule_type,
        schedule_at=payload.schedule_at,
        ended_at=payload.ended_at,
        batch_count=payload.batch_count,
        batch_interval_min=payload.batch_interval_min,
        randomize_content=int(payload.randomize_content),
        time_jitter_sec=payload.time_jitter_sec,
        pixel_degrade=int(payload.pixel_degrade),
        training_policy=payload.training_policy,
        training_redirect_url=payload.training_redirect_url,
        course_ids=payload.course_ids or [],
        force_training_rules=payload.force_training_rules or [],
        auth_confirmed=1,
        auth_snapshot=payload.auth_snapshot or [],
        wecom_template_id=payload.wecom_template_id,
        status="scheduled" if payload.schedule_type == "timed" else "draft",
    )
    db.add(campaign)
    db.flush()  # 取自增 id
    cid = campaign.id

    # 附件载荷关联（直发模式）
    _sync_campaign_attachments(db, cid, payload.attachment_ids or [])

    # 企微演练：无 userid 被跳过目标即时告警（目标展开告警）
    _alert_skipped_wecom(db, cid, skipped)

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


def duplicate_campaign(db, account, campaign_id: int) -> int:
    """复制演练：基于原演练配置创建新草稿（目标按快照重新展开）。"""
    src = _get_or_404(db, account, campaign_id)
    payload_snapshot = src.target_snapshot or {}
    if src.type == "social":
        user_ids, skipped = _resolve_wecom_targets(db, src.target_mode, payload_snapshot)
    else:
        user_ids = _expand_target_ids(db, src.target_mode, payload_snapshot) if payload_snapshot else []
        skipped = []

    new = Campaign(
        name=f"{src.name}（副本）",
        description=src.description,
        type=src.type,
        status="draft",
        creator_id=account.id,
        template_id=src.template_id,
        landing_page_id=src.landing_page_id,
        channel_id=src.channel_id,
        sender_profile_id=src.sender_profile_id,
        track_base_url=src.track_base_url,
        landing_base_url=src.landing_base_url,
        target_mode=src.target_mode,
        target_snapshot=payload_snapshot,
        target_count=len(user_ids),
        schedule_type="now",
        batch_count=src.batch_count,
        batch_interval_min=src.batch_interval_min,
        randomize_content=src.randomize_content,
        time_jitter_sec=src.time_jitter_sec,
        pixel_degrade=src.pixel_degrade,
        training_policy=src.training_policy,
        course_ids=src.course_ids or [],
        force_training_rules=src.force_training_rules or [],
        auth_confirmed=1,
        auth_snapshot=src.auth_snapshot or [],
        wecom_template_id=src.wecom_template_id,
    )
    db.add(new)
    db.flush()
    # 复制原演练的附件载荷关联
    src_attach = [r[0] for r in db.execute(
        select(CampaignAttachment.payload_id)
        .where(CampaignAttachment.campaign_id == src.id)).all()]
    _sync_campaign_attachments(db, new.id, src_attach)
    _alert_skipped_wecom(db, new.id, skipped)
    for i, uid in enumerate(user_ids):
        db.add(CampaignTarget(
            campaign_id=new.id,
            user_id=uid,
            batch_no=(i % (src.batch_count or 1)) + 1,
            token=secrets.token_hex(16),
        ))
    db.add(CampaignStat(campaign_id=new.id))
    db.commit()
    record_audit(
        db, account=account, module="campaign", action="duplicate",
        target_type="campaign", target_id=str(new.id),
        detail={"source_id": campaign_id, "name": new.name},
    )
    return new.id


def get_campaign(db, account, campaign_id: int):
    """演练详情（7 步向导回显）。"""
    c = _get_or_404(db, account, campaign_id)
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
        "auth_snapshot": c.auth_snapshot or [],
        "wecom_template_id": c.wecom_template_id,
        "target_mode": c.target_mode,
        "target_snapshot": c.target_snapshot or {},
        "template_id": c.template_id,
        "landing_page_id": c.landing_page_id,
        "channel_id": c.channel_id,
        "sender_profile_id": c.sender_profile_id,
        "track_base_url": c.track_base_url,
        "landing_base_url": c.landing_base_url,
        "started_at": _dt(c.started_at),
        "ended_at": _dt(c.ended_at),
        "created_at": _dt(c.created_at),
        "attachments": _campaign_attachments(db, c.id),
    }


def update_draft(db, account, campaign_id: int, payload, request_host: str | None = None):
    """向导草稿暂存（仅 draft/scheduled 可编辑，不触碰状态/目标数）。"""
    c = _get_or_404(db, account, campaign_id)
    if c.status not in ("draft", "scheduled"):
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅草稿/待开始状态可编辑")

    if payload.type == "social":
        _validate_wecom_campaign(db, payload)
    c.name = payload.name
    c.description = payload.description
    c.type = payload.type
    c.template_id = payload.template_id
    c.landing_page_id = payload.landing_page_id
    c.channel_id = payload.channel_id
    c.sender_profile_id = payload.sender_profile_id
    c.track_base_url, c.landing_base_url = _validate_base_urls(payload, request_host)
    c.target_mode = payload.target_mode
    c.target_snapshot = payload.target_snapshot or {}
    c.schedule_type = payload.schedule_type
    c.schedule_at = payload.schedule_at
    _validate_time_range(payload.schedule_type, payload.schedule_at, payload.ended_at)
    c.ended_at = payload.ended_at
    c.batch_count = payload.batch_count
    c.batch_interval_min = payload.batch_interval_min
    c.randomize_content = int(payload.randomize_content)
    c.time_jitter_sec = payload.time_jitter_sec
    c.pixel_degrade = int(payload.pixel_degrade)
    c.training_policy = payload.training_policy
    c.training_redirect_url = payload.training_redirect_url
    c.course_ids = payload.course_ids or []
    c.force_training_rules = payload.force_training_rules or []
    c.auth_confirmed = int(payload.auth_confirmed)
    c.auth_snapshot = payload.auth_snapshot or []
    c.wecom_template_id = payload.wecom_template_id
    # 附件载荷关联（先清后写，幂等）
    _sync_campaign_attachments(db, campaign_id, payload.attachment_ids or [])
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="update_draft",
        target_type="campaign", target_id=str(campaign_id),
        detail={"name": payload.name},
    )
    return None


def start(db, account, campaign_id: int):
    """draft/scheduled → sending（投递中）：生成批次调度并派发 Worker 投递。

    投递完毕（无 pending/sending 批次）由派发器 dispatch_due_batches 自动转
    running（追踪期），故 running 语义收敛为「投递完成、追踪中」。

    原子认领（UPDATE ... WHERE status IN (draft,scheduled)）：手动启动与
    自动启动（campaign_auto.start_scheduled）并发时仅一方成功，避免重复生成批次。
    """
    now = datetime.now()
    c = db.get(Campaign, campaign_id)
    if c is None:
        raise BizError(ErrorCode.NOT_FOUND)
    # 企微演练启动前重校验（红线4：无授权不可启动；通道缺失提前拦截，避免批次派发后整批失败）
    if c.type == "social":
        if not c.auth_confirmed:
            raise BizError(ErrorCode.PARAM_INVALID, "演练未勾选授权，不可启动（红线4）")
        missing = [k for k in _WECOM_AUTH_REQUIRED if k not in (c.auth_snapshot or [])]
        if missing:
            labels = "、".join(_WECOM_AUTH_LABELS.get(k, k) for k in missing)
            raise BizError(ErrorCode.PARAM_INVALID, f"企微演练授权条款不完整，不可启动（缺：{labels}）")
        from app.modules.channel.models import SendChannel

        ch = db.get(SendChannel, c.channel_id) if c.channel_id else None
        if ch is not None and ch.type != "wecom":
            raise BizError(ErrorCode.PARAM_INVALID, "企微演练的发送通道须为企业微信类型")
        if ch is None and db.scalar(select(SendChannel).where(
                SendChannel.type == "wecom").order_by(SendChannel.is_default.desc(), SendChannel.id)) is None:
            raise BizError(ErrorCode.PARAM_INVALID, "无可用企业微信发送通道，请先在「发送配置」创建企微通道")
    claimed = db.execute(
        update(Campaign)
        .where(Campaign.id == campaign_id, Campaign.status.in_(("draft", "scheduled")))
        .values(status="sending", started_at=now)
    )
    if claimed.rowcount == 0:
        db.rollback()
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅草稿/待开始状态可启动")
    # 批次行：Worker 按 plan_at 触发投递，uk_campaign_batch 保证幂等；
    # 状态变更与批次生成同事务提交，失败整体回滚不留 running 无批次
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

    # Webhook 告警推送：演练开始
    try:
        from app.modules.integration.service import notify_webhooks

        notify_webhooks(db, "campaign_start", {
            "演练名称": c.name, "目标人数": c.target_count, "演练类型": c.type,
        })
    except Exception:
        pass  # 推送失败不阻断启动

    # 投递派发：Worker 在线时立即开始投递；离线时由 beat 每 30s 兜底扫描
    try:
        from worker.tasks.delivery import dispatch_due_batches

        dispatch_due_batches.delay()
    except Exception:
        pass
    return None


def pause(db, account, campaign_id: int):
    """sending/running → paused：停止批次调度，追踪链路继续。"""
    c = _get_or_404(db, account, campaign_id)
    if c.status not in ("sending", "running"):
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅发送中/运行中状态可暂停")
    c.status = "paused"
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="pause",
        target_type="campaign", target_id=str(campaign_id),
    )
    return None


def resume(db, account, campaign_id: int):
    """paused → sending/running：恢复批次调度（有未投批次回发送中，否则直接回追踪中）。"""
    c = _get_or_404(db, account, campaign_id)
    if c.status != "paused":
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅暂停状态可恢复")
    has_pending = db.scalar(
        select(CampaignBatch.id)
        .where(
            CampaignBatch.campaign_id == campaign_id,
            CampaignBatch.status.in_(("pending", "sending")),
        )
        .limit(1)
    )
    c.status = "sending" if has_pending else "running"
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="resume",
        target_type="campaign", target_id=str(campaign_id),
    )
    return None


def terminate(db, account, campaign_id: int):
    """非终态 → terminated：停止发送与追踪，写审计。"""
    c = _get_or_404(db, account, campaign_id)
    if c.status not in ("draft", "scheduled", "sending", "running", "paused"):
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "当前状态不可终止")
    c.status = "terminated"
    c.ended_at = datetime.now()
    db.commit()

    record_audit(
        db, account=account, module="campaign", action="terminate",
        target_type="campaign", target_id=str(campaign_id),
    )

    # Webhook 告警推送：演练结束
    try:
        from app.modules.integration.service import notify_webhooks

        notify_webhooks(db, "campaign_end", {"演练名称": c.name, "结束方式": "手动终止"})
    except Exception:
        pass  # 推送失败不阻断终止
    return None


def dashboard(db, account, campaign_id: int) -> dict:
    """监控大屏：指标卡 + 漏斗 + 预警。

    口径：已阅读/已点击/中招/举报均为「人数」（去重目标），
    打开过即计 1 人，重复打开不重复计数；投递成功为实际送达目标数。
    """
    c = _get_or_404(db, account, campaign_id)
    stat = db.get(CampaignStat, campaign_id)
    # 投递成功按目标实时口径（delivered_cnt 只在投递时累加，退信纠正为
    # bounced/failed 后不会回减；sent 即"已发出且尚未收到退信"的真实在途数）
    delivered = int(db.scalar(
        select(func.count()).select_from(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.send_status == "sent",
        )
    ) or 0)
    submitted = stat.submit_cnt if stat else 0
    reported = stat.report_cnt if stat else 0
    target = c.target_count or 1

    # 打开/点击按人数口径：目标明细中 open_count/click_count > 0 的去重目标数
    opened = int(db.scalar(
        select(func.count()).select_from(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.open_count > 0,
        )
    ) or 0)
    clicked = int(db.scalar(
        select(func.count()).select_from(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.click_count > 0,
        )
    ) or 0)
    # 附件运行（打开附件）：人数口径，与 open/click 一致
    attached = int(db.scalar(
        select(func.count()).select_from(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.attach_run_count > 0,
        )
    ) or 0)
    # 中招口径（去重人数）：提交数据 + 附件运行，同人双行为不重复计
    victim_cnt = int(db.scalar(
        select(func.count()).select_from(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            or_(CampaignTarget.submit_flag == 1, CampaignTarget.attach_run_count > 0),
        )
    ) or 0)

    metrics = [
        {"label": "投递总数", "value": target, "suffix": "", "accent": "blue"},
        {"label": "投递成功", "value": delivered, "suffix": "", "accent": "purple"},
        {"label": "已阅读", "value": opened, "suffix": "", "accent": "teal"},
        {"label": "已点击", "value": clicked, "suffix": "", "accent": "orange"},
        {"label": "中招人数", "value": victim_cnt, "suffix": "", "accent": "red"},
        {"label": "已举报", "value": reported, "suffix": "", "accent": "green"},
    ]

    # 漏斗：投递总数 → 投递成功 → 行为环节；投递成功相对总数折算，后续相对投递成功折算
    base = delivered or 1
    funnel = [
        {"name": "投递总数", "value": target, "rate": "100%"},
        {"name": "投递成功", "value": delivered, "rate": f"{delivered / target * 100:.1f}%"},
        {"name": "已阅读", "value": opened, "rate": f"{opened / base * 100:.1f}%"},
        {"name": "已点击", "value": clicked, "rate": f"{clicked / base * 100:.1f}%"},
        {"name": "附件运行", "value": attached, "rate": f"{attached / base * 100:.1f}%"},
        {"name": "输入数据", "value": submitted, "rate": f"{submitted / base * 100:.1f}%"},
        {"name": "已举报", "value": reported, "rate": f"{reported / base * 100:.1f}%"},
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


def _parse_ua(ua: str | None) -> str:
    """User-Agent → 「浏览器 版本 · 系统」简写；无法识别时返回原始 UA。"""
    import re

    if not ua:
        return ""
    browser = ""
    os = ""
    if "Edg/" in ua:
        m = re.search(r"Edg/([\d.]+)", ua)
        browser = f"Edge {m.group(1) if m else ''}".strip()
    elif "Chrome/" in ua:
        m = re.search(r"Chrome/([\d.]+)", ua)
        browser = f"Chrome {m.group(1) if m else ''}".strip()
    elif "Firefox/" in ua:
        m = re.search(r"Firefox/([\d.]+)", ua)
        browser = f"Firefox {m.group(1) if m else ''}".strip()
    elif "Safari/" in ua and "Version/" in ua:
        m = re.search(r"Version/([\d.]+)", ua)
        browser = f"Safari {m.group(1) if m else ''}".strip()
    if "Windows NT 10" in ua:
        os = "Windows 10/11"
    elif "Windows NT 6" in ua:
        os = "Windows 7/8"
    elif "Mac OS X" in ua:
        os = "macOS"
    elif "iPhone" in ua:
        os = "iOS"
    elif "Android" in ua:
        os = "Android"
    elif "Linux" in ua:
        os = "Linux"
    if browser and os:
        return f"{browser} · {os}"
    if browser:
        return browser
    return ua.split()[0]


def timeline(db, account, campaign_id: int, page: int, page_size: int):
    """用户行为时间轴：track_event left join emp_user/emp_dept，附 IP/UA/指纹/提交脱敏详情。"""
    _get_or_404(db, account, campaign_id)  # 数据权限校验（与详情同口径）
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

    # 指纹哈希批量联查（fp_hash 32 位完整展示）
    fp_ids = {ev.fingerprint_id for ev, *_ in rows if ev.fingerprint_id}
    fp_map = {}
    if fp_ids:
        from app.modules.tracking.models import Fingerprint

        fp_map = {
            f.id: f.fp_hash
            for f in db.scalars(select(Fingerprint).where(Fingerprint.id.in_(fp_ids))).all()
        }

    items = []
    for ev, user_name, dept_name in rows:
        if user_name:
            user = f"{user_name} · {dept_name}" if dept_name else user_name
        else:
            user = "未知用户"
        items.append({
            "id": ev.id,
            "time": ev.created_at.strftime(_DT_FMT) if ev.created_at else "",
            "user": user,
            "action": _ACTION_TEXT.get(ev.event_type, ev.event_type),
            "icon": _ACTION_ICON.get(ev.event_type, "•"),
            "ip": ev.ip or "",
            "browser": _parse_ua(ev.ua),
            "fingerprint": fp_map.get(ev.fingerprint_id, ""),
            "detail": ev.detail or {},
            "danger": ev.event_type in ("submit", "attach_run"),
            "good": ev.event_type == "report",
        })
    return {"list": items, "total": total, "page": page, "pageSize": page_size}


def delivery_failures(db, account, campaign_id: int, page: int, page_size: int):
    """投递失败列表：campaign_target 状态为 failed/bounced，附收件人邮箱/姓名/失败原因。"""
    _get_or_404(db, account, campaign_id)  # 数据权限校验（与详情同口径）
    base = (
        select(CampaignTarget, EmpUser.name, EmpUser.email)
        .outerjoin(EmpUser, EmpUser.id == CampaignTarget.user_id)
        .where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.send_status.in_(("failed", "bounced")),
        )
    )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.execute(
        base.order_by(CampaignTarget.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "id": t.id,
            "name": name or f"员工#{t.user_id}",
            "email": email or "",
            "status": t.send_status,
            "reason": t.fail_reason or "",
            "time": (t.sent_at or t.updated_at).strftime(_DT_FMT) if (t.sent_at or t.updated_at) else "",
        }
        for t, name, email in rows
    ]
    return {"list": items, "total": total, "page": page, "pageSize": page_size}


def reveal_submit_password(db, account, campaign_id: int, event_id: int,
                           operation_password: str) -> dict:
    """取证：管理端输入操作密码后解密提交事件的全部明文（AES-GCM），全程审计。

    操作密码存 PBKDF2 哈希（settings.reveal_operation_pwd），配置前无法取证。
    仅 submit 事件可解密；无密文（历史数据/加密失败）时提示无法求证。
    """
    import base64

    _get_or_404(db, account, campaign_id)  # 数据权限校验：禁止跨范围取证

    from app.core.security import decrypt_secret, verify_password
    from app.modules.settings.service import get_setting

    stored = get_setting(db, "reveal_operation_pwd", "")
    if not stored:
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "未配置取证操作密码，请在系统设置中配置后再试")
    if not verify_password(operation_password, stored):
        raise BizError(ErrorCode.PERM_DENIED, "取证操作密码错误")

    ev = db.get(TrackEvent, event_id)
    if ev is None or ev.campaign_id != campaign_id:
        raise BizError(ErrorCode.NOT_FOUND, "事件不存在")
    if ev.event_type != "submit":
        raise BizError(ErrorCode.PARAM_INVALID, "仅提交事件可取证")

    # 解密全部 *_plain 密文字段（口令/账号/手机号/验证码等）
    fields: list[dict] = []
    detail = ev.detail or {}
    for key, value in detail.items():
        if not key.endswith("_plain") or not isinstance(value, dict) or not value.get("encrypted"):
            continue
        try:
            plain = decrypt_secret(base64.b64decode(value["encrypted"]))
        except Exception:
            continue
        fields.append({"name": key[: -len("_plain")], "value": plain})
    if not fields:
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "该事件未加密存储明文，无法取证")

    user = db.get(EmpUser, ev.user_id)
    record_audit(
        db, account=account, module="campaign", action="reveal_password",
        target_type="track_event", target_id=str(event_id),
        detail={"campaign_id": campaign_id, "user": user.name if user else ev.user_id,
                "fields": [f["name"] for f in fields]},
    )
    return {"fields": fields, "event_id": event_id, "user": user.name if user else None}


def test_send(db, account, campaign_id: int, to: list[str]) -> dict:
    """发送测试：按演练绑定的 SMTP 通道真实投递到白名单收件人。

    内容复用 render_campaign_email（与 Worker 批量投递一致：模板变量、落地页链接、
    追踪像素、二维码），保证测试邮件与真实演练邮件完全一致。
    """
    from app.core.security import decrypt_secret
    from app.modules.campaign.render import render_campaign_email
    from app.modules.channel.models import SendChannel, SenderProfile
    from app.modules.channel.service import _smtp_send

    addrs = [(a or "").strip() for a in to]
    addrs = [a for a in addrs if a]
    if not addrs:
        raise BizError(ErrorCode.PARAM_INVALID, "请至少提供一个收件人邮箱地址")

    c = _get_or_404(db, account, campaign_id)

    # 通道解析：演练绑定通道 → 默认 SMTP 通道
    ch = db.get(SendChannel, c.channel_id) if c.channel_id else None
    if ch is None or ch.type != "smtp" or ch.status == "disabled":
        ch = db.scalar(
            select(SendChannel)
            .where(
                SendChannel.type == "smtp",
                SendChannel.status != "disabled",
                SendChannel.is_default == 1,
            )
            .order_by(SendChannel.id)
        )
    if ch is None or not ch.smtp_host:
        raise BizError(ErrorCode.PARAM_INVALID, "未配置可用 SMTP 通道，请先在发件配置中添加并完成连通测试")

    password = ""
    if ch.smtp_password_enc:
        try:
            password = decrypt_secret(ch.smtp_password_enc)
        except Exception:
            password = ""
    cfg = {
        "smtp_host": ch.smtp_host,
        "smtp_port": ch.smtp_port,
        "smtp_encrypt": ch.smtp_encrypt,
        "smtp_username": ch.smtp_username,
        "smtp_password": password,
    }

    # 伪装发件人 From 地址（仅影响收件端展示，信封仍用通道账号）；显示名由渲染逻辑处理
    from_addr = None
    if c.sender_profile_id:
        sp = db.get(SenderProfile, c.sender_profile_id)
        if sp:
            from_addr = sp.from_addr

    results = []
    for addr in addrs:
        try:
            rendered = render_campaign_email(db, c, None, secrets.token_hex(16), to=addr)
            r = _smtp_send(
                ch.name, cfg, addr,
                subject=rendered["subject"], html_body=rendered["html"],
                sender_name=rendered["sender_name"], from_addr=from_addr,
                attachments=rendered["attachments"],
            )
            ok = bool(r.get("ok"))
        except Exception as err:  # 通道适配器内部异常兜底，逐收件人记录
            ok = False
            r = {"ok": False, "message": f"发送异常：{err}"}
        results.append({"to": addr, "ok": ok, "message": r.get("message", "")})

    ok_cnt = sum(1 for r in results if r["ok"])
    record_audit(
        db, account=account, module="campaign", action="test_send",
        target_type="campaign", target_id=str(campaign_id),
        detail={"recipients": len(addrs), "ok": ok_cnt, "results": results},
    )
    return {
        "ok": ok_cnt == len(results),
        "message": f"成功 {ok_cnt}/{len(results)}，详见逐收件人结果",
        "results": results,
    }


def delete_campaign(db, account, campaign_id: int) -> None:
    """删除演练：草稿/待开始/已终止状态可删（进行中不可删，避免追踪事件孤儿；已完成保留报表不删）；关联数据级联删除。

    追踪事件（TrackEvent）一并级联：档案"历史中招"（emp_risk_profile.phish_count
    快照）与轨迹均以 track_event 为源，残留事件会造成"演练已删、档案仍有中招"的假象。
    删除后对受影响员工重算画像，保证快照与剩余事件一致。
    """
    c = _get_or_404(db, account, campaign_id)
    if c.status not in ("draft", "scheduled", "terminated"):
        raise BizError(ErrorCode.CAMPAIGN_STATE_INVALID, "仅草稿/待开始/已终止状态可删除演练")
    affected = [
        uid for (uid,) in db.execute(
            select(TrackEvent.user_id).where(
                TrackEvent.campaign_id == campaign_id,
                TrackEvent.user_id.isnot(None),
            ).distinct()
        ).all()
    ]
    db.execute(TrackEvent.__table__.delete().where(TrackEvent.campaign_id == campaign_id))
    db.execute(CampaignTarget.__table__.delete().where(CampaignTarget.campaign_id == campaign_id))
    db.execute(CampaignBatch.__table__.delete().where(CampaignBatch.campaign_id == campaign_id))
    db.execute(CampaignStat.__table__.delete().where(CampaignStat.campaign_id == campaign_id))
    db.execute(CampaignAlert.__table__.delete().where(CampaignAlert.campaign_id == campaign_id))
    db.execute(CampaignAttachment.__table__.delete().where(CampaignAttachment.campaign_id == campaign_id))
    db.delete(c)
    db.commit()
    # 受影响员工画像重算（与 track_stream/risk_recalc 同口径：中招=submit+attach_run）；
    # 同步执行量小，失败降级只告警不阻断删除
    for uid in affected:
        try:
            from worker.tasks.risk_recalc import recalc
            recalc(uid)
        except Exception:
            logger.warning("recalc after campaign delete failed uid=%s cid=%s", uid, campaign_id)
    record_audit(
        db, account=account, module="campaign", action="delete_campaign",
        target_type="campaign", target_id=str(campaign_id),
    )
