"""演练自动完成：到达计划结束时间 → completed。

投递完毕后演练保持 running（追踪期）：打开/点击/中招事件继续采集，
直到 ended_at（未设置时按开始时间 +7 天追踪期）才自动关闭。
幂等：仅扫描 running 状态。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.campaign_auto")

_DEFAULT_TRACKING_DAYS = 7


@celery_app.task(name="worker.tasks.campaign_auto.auto_complete")
def auto_complete() -> int:
    """扫描 running 演练，到期（ended_at <= now）置 completed 并审计 + 推送 webhook。

    结束时间口径与列表页展示一致：ended_at 未设置时按开始时间 +7 天追踪期兜底
    （列表页也是「无结束时间按开始+7天」）。
    """
    from app.core.audit import record_audit
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign

    db = SessionLocal()
    try:
        campaigns = db.scalars(select(Campaign).where(Campaign.status == "running")).all()
        if not campaigns:
            return 0
        now = datetime.now()
        completed = 0
        for c in campaigns:
            deadline = c.ended_at or (
                (c.started_at or c.created_at) + timedelta(days=_DEFAULT_TRACKING_DAYS)
            )
            if deadline > now:
                continue  # 追踪期内：事件继续采集

            c.status = "completed"
            c.ended_at = c.ended_at or deadline
            db.commit()
            record_audit(
                db, account=None, module="campaign", action="auto_complete",
                target_type="campaign", target_id=str(c.id),
                detail={"name": c.name, "reason": "到期"},
            )
            try:
                from app.modules.integration.service import notify_webhooks

                notify_webhooks(db, "campaign_end",
                                {"演练名称": c.name, "结束方式": "到期自动完成"})
            except Exception:  # 推送失败不阻断自动完成
                pass
            completed += 1
            logger.info("campaign %s auto completed (到期)", c.id)
        return completed
    finally:
        db.close()
