"""追踪事件消费者：evt:stream → track_event 落库 + 计数回写 + 高危预警。

Beat 每 10 秒调度；消费组 + ACK 保证至少一次投递，事件按 token 幂等去重
（同 token+event_type+10 分钟窗口内重复事件丢弃）。
"""
import json
import logging
from datetime import datetime, timedelta

import redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.tracking.stream import ack, read_pending
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.track")

_EVENT_CN = {
    "open": "打开了邮件",
    "click": "点击了邮件中的链接",
    "submit": "在登录页提交了账号密码",
    "report": "举报了可疑邮件",
    "attach_run": "运行了附件",
    "bounce": "邮件被退回",
}


@celery_app.task(name="worker.tasks.track_stream.consume")
def consume():
    """拉取一批事件落库（最多 200 条/次）。"""
    from sqlalchemy import select

    from app.modules.campaign.models import Campaign, CampaignAlert, CampaignStat, CampaignTarget
    from app.modules.org.models import EmpDept, EmpUser
    from app.modules.tracking.models import TrackEvent

    r = redis.from_url(settings.redis_url, decode_responses=True)
    events = read_pending(r, count=200)
    if not events:
        return 0

    db = SessionLocal()
    acked: list[str] = []
    try:
        for event_id, fields in events:
            acked.append(event_id)
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

            target = db.scalar(select(CampaignTarget).where(CampaignTarget.token == token))
            if target is None:
                continue  # 未知 token（预览邮件等）：丢弃
            campaign = db.get(Campaign, target.campaign_id)
            if campaign is None:
                continue
            user = db.get(EmpUser, target.user_id)
            dept = db.get(EmpDept, user.dept_id) if user else None

            # 事件去重：同 token+event_type 60 秒窗口内只计一次
            # （防邮件客户端/图片代理同一时刻重复请求像素导致统计虚高）
            dup = db.scalar(
                select(TrackEvent.id).where(
                    TrackEvent.token == token,
                    TrackEvent.event_type == event_type,
                    TrackEvent.created_at >= ts - timedelta(seconds=60),
                ).limit(1)
            )
            if dup is not None:
                continue

            # 指纹：detail 携带 fp_hash 时 upsert fingerprint 表并关联
            fingerprint_id = None
            fp_hash = detail.get("fp_hash") if isinstance(detail, dict) else None
            if fp_hash:
                fp_hash = str(fp_hash)[:32]  # fp_hash 列 VARCHAR(32)，防御超长
                from app.modules.tracking.models import Fingerprint

                fp = db.scalar(select(Fingerprint).where(Fingerprint.fp_hash == fp_hash))
                if fp is None:
                    fp = Fingerprint(fp_hash=fp_hash, first_seen_at=ts, last_seen_at=ts, seen_count=1)
                    db.add(fp)
                    db.flush()
                else:
                    fp.last_seen_at = ts
                    fp.seen_count += 1
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

            # 目标明细计数
            if event_type == "open":
                target.open_count += 1
                target.first_open_at = target.first_open_at or ts
                target.last_open_at = ts
            elif event_type == "click":
                target.click_count += 1
                target.first_click_at = target.first_click_at or ts
            elif event_type == "submit":
                target.submit_flag = 1
                target.submit_at = target.submit_at or ts
            elif event_type == "report":
                target.report_flag = 1
                target.report_at = target.report_at or ts

            # 冗余计数
            stat = db.get(CampaignStat, campaign.id)
            if stat is None:
                stat = CampaignStat(campaign_id=campaign.id)
                db.add(stat)
            if event_type == "open":
                stat.open_cnt += 1
            elif event_type == "click":
                stat.click_cnt += 1
            elif event_type == "submit":
                stat.submit_cnt += 1
            elif event_type == "report":
                stat.report_cnt += 1

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

            # 员工风险画像实时更新（每日全量重算由 risk_recalc 兜底）
            from app.modules.org.models import EmpRiskProfile

            profile = db.get(EmpRiskProfile, target.user_id)
            if profile is None:
                profile = EmpRiskProfile(user_id=target.user_id)
                db.add(profile)
                db.flush()
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
            # 综合评分公式与 org 服务共享（五维风险均值，举报意识反向）
            from app.modules.org.service import _risk_level_of, _total_from_dims

            profile.total_score = _total_from_dims(
                profile.email_recognize, profile.link_click, profile.pwd_submit,
                profile.attach_run, profile.report_awareness,
            )
            profile.risk_level = _risk_level_of(profile.total_score)

        db.commit()
        ack(r, acked)
        logger.info("track consume: %d events processed", len(events))
        return len(events)
    except Exception:
        db.rollback()
        # 不 ACK：消费组重放未确认消息，避免丢失
        raise
    finally:
        db.close()
