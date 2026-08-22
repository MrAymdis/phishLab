"""追踪事件消费者：evt:stream → track_event 落库 + 计数回写 + 高危预警。

Beat 每 10 秒调度；消费组 + ACK 保证至少一次投递，事件按 token 幂等去重
（同 token+event_type+60 秒窗口内重复事件丢弃）。

千人规模优化：整批事件（≤200 条/次）共享实体预加载——target/campaign/user/dept/
stat/profile/fingerprint/行为计数/去重窗口各一次 IN 查询，替代逐事件 8+ 次查询。
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import redis
from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.tracking.stream import ack, read_pending
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.track")

_DEDUP_WINDOW_SEC = 60

_EVENT_CN = {
    "open": "打开了邮件",
    "click": "点击了邮件中的链接",
    "submit": "在登录页提交了敏感数据",
    "report": "举报了可疑邮件",
    "attach_run": "运行了附件",
    "bounce": "邮件被退回",
}
_EVENT_ICON = {
    "open": "📧",
    "click": "🔗",
    "submit": "⚠️",
    "report": "🛡️",
    "attach_run": "📎",
    "bounce": "↩️",
}


@celery_app.task(name="worker.tasks.track_stream.consume")
def consume():
    """拉取一批事件落库（最多 200 条/次），共享实体批量预加载。"""
    from app.modules.campaign.models import Campaign, CampaignAlert, CampaignStat, CampaignTarget
    from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
    from app.modules.org.service import _risk_level_of, _total_from_behavior
    from app.modules.tracking.models import Fingerprint, TrackEvent

    r = redis.from_url(settings.redis_url, decode_responses=True)
    events = read_pending(r, count=200)
    if not events:
        return 0

    # 解析事件
    parsed = []
    for event_id, fields in events:
        token = fields.get("token") or ""
        event_type = fields.get("event_type") or ""
        try:
            detail = json.loads(fields.get("detail") or "{}")
        except (json.JSONDecodeError, TypeError):
            detail = {}
        ts = datetime.now()
        try:
            ts = datetime.fromisoformat(fields.get("ts") or "")
        except ValueError:
            pass
        parsed.append((event_id, token, event_type, detail, ts, fields))

    db = SessionLocal()
    acked: list[str] = []
    batch_events: dict[int, list[dict]] = {}  # campaign_id → 待推送事件（SSE）
    try:
        tokens = [p[1] for p in parsed]
        targets = {t.token: t for t in db.scalars(
            select(CampaignTarget).where(CampaignTarget.token.in_(tokens))).all()}
        cids = {t.campaign_id for t in targets.values()}
        campaigns = {c.id: c for c in db.scalars(
            select(Campaign).where(Campaign.id.in_(cids))).all()} if cids else {}
        uids = {t.user_id for t in targets.values()}
        users = {u.id: u for u in db.scalars(
            select(EmpUser).where(EmpUser.id.in_(uids))).all()} if uids else {}
        dept_ids = {u.dept_id for u in users.values() if u.dept_id}
        depts = {d.id: d for d in db.scalars(
            select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}
        profiles = {p.user_id: p for p in db.scalars(
            select(EmpRiskProfile).where(EmpRiskProfile.user_id.in_(uids))).all()} if uids else {}
        # 行为计数预加载（替代每事件 _behavior_counts 聚合查询；本批事件内存增量）
        behavior: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        if uids:
            for uid, et, n in db.execute(
                select(TrackEvent.user_id, TrackEvent.event_type, func.count(TrackEvent.id))
                .where(TrackEvent.user_id.in_(uids))
                .group_by(TrackEvent.user_id, TrackEvent.event_type)
            ).all():
                behavior[uid][et] = int(n or 0)
        # 去重窗口预加载：每 (token, event_type) 最近事件时间（一条 GROUP BY 替代逐条 SELECT）
        min_ts = min(p[4] for p in parsed)
        dup_map: dict[tuple[str, str], datetime] = {}
        if tokens:
            for token, et, max_ts in db.execute(
                select(TrackEvent.token, TrackEvent.event_type, func.max(TrackEvent.created_at))
                .where(TrackEvent.token.in_(tokens),
                       TrackEvent.created_at >= min_ts - timedelta(seconds=_DEDUP_WINDOW_SEC))
                .group_by(TrackEvent.token, TrackEvent.event_type)
            ).all():
                dup_map[(token, et)] = max_ts
        # 指纹预加载
        fp_hashes = {
            str(d.get("fp_hash"))[:32]
            for _, _, _, d, _, _ in parsed
            if isinstance(d, dict) and d.get("fp_hash")
        }
        fps = {f.fp_hash: f for f in db.scalars(
            select(Fingerprint).where(Fingerprint.fp_hash.in_(fp_hashes))).all()} if fp_hashes else {}

        # 批内去重（同 token+event_type 60s 窗口，原语义逐条可见）
        batch_seen: dict[tuple[str, str], datetime] = {}

        for event_id, token, event_type, detail, ts, fields in parsed:
            acked.append(event_id)
            target = targets.get(token)
            if target is None:
                continue  # 未知 token（预览邮件等）：丢弃
            campaign = campaigns.get(target.campaign_id)
            if campaign is None:
                continue
            user = users.get(target.user_id)
            dept = depts.get(user.dept_id) if user and user.dept_id else None

            # 事件去重：同 token+event_type 60 秒窗口内只计一次
            key = (token, event_type)
            recent = dup_map.get(key)
            if recent is not None and recent >= ts - timedelta(seconds=_DEDUP_WINDOW_SEC):
                continue
            seen_ts = batch_seen.get(key)
            if seen_ts is not None and seen_ts >= ts - timedelta(seconds=_DEDUP_WINDOW_SEC):
                continue
            batch_seen[key] = ts

            # 指纹：detail 携带 fp_hash 时 upsert fingerprint 表并关联
            fingerprint_id = None
            fp_hash = detail.get("fp_hash") if isinstance(detail, dict) else None
            if fp_hash:
                fp_hash = str(fp_hash)[:32]  # fp_hash 列 VARCHAR(32)，防御超长
                fp = fps.get(fp_hash)
                if fp is None:
                    fp = Fingerprint(
                        fp_hash=fp_hash, first_seen_at=ts, last_seen_at=ts, seen_count=1,
                        detail=detail.get("fp") if isinstance(detail.get("fp"), dict) else None,
                    )
                    db.add(fp)
                    fps[fp_hash] = fp
                else:
                    fp.last_seen_at = ts
                    fp.seen_count += 1
                    # 旧指纹补快照：首见于 detail 功能上线前，本次事件携带原始组件则回填
                    if fp.detail is None and isinstance(detail.get("fp"), dict):
                        fp.detail = detail["fp"]
                fingerprint_id = fp.id

            db.add(TrackEvent(
                campaign_id=campaign.id,
                user_id=target.user_id,
                token=token,
                event_type=event_type,
                ip=fields.get("ip") or None,
                ua=fields.get("ua") or None,
                fingerprint_id=fingerprint_id,
                detail=detail,
                created_at=ts,  # 事件原始时间（去重窗口与时间轴均按此比较，而非落库时间）
            ))

            # 目标明细计数（事件次数）
            first_open = first_click = first_submit = first_report = False
            if event_type == "open":
                first_open = target.open_count == 0
                target.open_count += 1
                target.first_open_at = target.first_open_at or ts
                target.last_open_at = ts
            elif event_type == "click":
                first_click = target.click_count == 0
                target.click_count += 1
                target.first_click_at = target.first_click_at or ts
            elif event_type == "submit":
                first_submit = target.submit_flag == 0
                target.submit_flag = 1
                target.submit_at = target.submit_at or ts
            elif event_type == "report":
                first_report = target.report_flag == 0
                target.report_flag = 1
                target.report_at = target.report_at or ts

            # 冗余计数：人数字径（仅首次行为计入；原子累加防并发消费 lost update）
            inc_col = None
            if event_type == "open" and first_open:
                inc_col = "open_cnt"
            elif event_type == "click" and first_click:
                inc_col = "click_cnt"
            elif event_type == "submit" and first_submit:
                inc_col = "submit_cnt"
            elif event_type == "report" and first_report:
                inc_col = "report_cnt"
            if inc_col:
                stmt = insert(CampaignStat).values(campaign_id=campaign.id, **{inc_col: 1})
                db.execute(stmt.on_duplicate_key_update(
                    **{inc_col: getattr(CampaignStat, inc_col) + 1}))

            # 提交事件 → 高危预警
            if event_type == "submit" and user:
                db.add(CampaignAlert(
                    campaign_id=campaign.id,
                    type="pwd_submit",
                    level=3,
                    message=f"{user.name}（{dept.name if dept else '-'}）在演练落地页提交了账号密码，属高危行为",
                    target_user_id=user.id,
                ))
                logger.info("high-risk submit campaign=%s user=%s", campaign.id, user.name)
                # Webhook 告警推送：高危中招（推送失败不影响落库，由外层统一回滚保护）
                try:
                    from app.modules.integration.service import notify_webhooks

                    notify_webhooks(db, "high_risk", {
                        "演练": campaign.name,
                        "员工": f"{user.name}（{dept.name if dept else '-'}）",
                        "行为": "在落地页提交了账号密码",
                    })
                except Exception:
                    pass

            # 员工风险画像实时更新（每日全量重算由 risk_recalc 兜底）
            profile = profiles.get(target.user_id)
            if profile is None:
                profile = EmpRiskProfile(user_id=target.user_id)
                db.add(profile)
                profiles[target.user_id] = profile
            if event_type == "submit":
                profile.phish_count += 1
                profile.pwd_submit = min(100, profile.pwd_submit + 15)
            elif event_type == "click":
                profile.link_click = min(100, profile.link_click + 8)
            elif event_type == "open":
                profile.email_recognize = min(100, profile.email_recognize + 3)
            elif event_type == "report":
                profile.report_count += 1
                profile.report_awareness = min(100, profile.report_awareness + 10)
            # 综合评分：行为次数直接计分（预加载计数 + 本批增量；原语义含当前事件）
            b = behavior[target.user_id]
            if event_type in ("open", "click", "submit", "report"):
                b[event_type] += 1
            profile.total_score = _total_from_behavior(
                user.initial_risk if user else 70,
                b["open"], b["click"], b["submit"], b["report"],
            )
            profile.risk_level = _risk_level_of(profile.total_score)

            # 收集实时推送事件（SSE 详情页订阅 campaign_evt:{cid}）
            if user:
                user_label = f"{user.name} · {dept.name}" if dept else user.name
            else:
                user_label = "未知用户"
            batch_events.setdefault(campaign.id, []).append({
                "event_type": event_type,
                "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "user": user_label,
                "action": _EVENT_CN.get(event_type, event_type),
                "icon": _EVENT_ICON.get(event_type, "•"),
                "ip": fields.get("ip") or "",
                "danger": event_type == "submit",
                "good": event_type == "report",
            })

        db.commit()
        # 提交成功后再广播（失败不推送，前端仍可通过轮询兜底）
        if batch_events:
            pub = redis.from_url(settings.redis_url, decode_responses=True)
            pipe = pub.pipeline()
            for cid, evs in batch_events.items():
                for ev in evs:
                    pipe.publish(
                        f"campaign_evt:{cid}",
                        json.dumps({"type": "event", "data": ev}, ensure_ascii=False),
                    )
            pipe.execute()
        ack(r, acked)
        logger.info("track consume: %d events processed", len(events))
        return len(events)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
