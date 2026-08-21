"""演练自动完成：投递完毕或到达计划结束时间 → completed。

幂等：仅扫描 running 状态；批量为空或仍有 pending/sending 时不动作。
"""
import logging
from datetime import datetime

from sqlalchemy import func, select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.campaign_auto")


@celery_app.task(name="worker.tasks.campaign_auto.auto_complete")
def auto_complete() -> int:
    """扫描 running 演练，满足任一条件置 completed 并审计 + 推送 webhook：
    - 全部批次已终态（done/failed，且无 pending/sending）
    - 到达计划结束时间 ended_at
    """
    from app.core.audit import record_audit
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignBatch

    db = SessionLocal()
    try:
        campaigns = db.scalars(select(Campaign).where(Campaign.status == "running")).all()
        if not campaigns:
            return 0
        now = datetime.now()
        completed = 0
        for c in campaigns:
            expired = bool(c.ended_at and c.ended_at <= now)
            stats = dict(db.execute(
                select(CampaignBatch.status, func.count(CampaignBatch.id))
                .where(CampaignBatch.campaign_id == c.id)
                .group_by(CampaignBatch.status)
            ).all())
            has_batches = bool(stats)
            delivery_done = (
                has_batches
                and not (stats.get("pending", 0) or stats.get("sending", 0))
                and (stats.get("done", 0) or stats.get("failed", 0))
            )
            if not (expired or delivery_done):
                continue

            reason = "到期" if expired else "投递完成"
            c.status = "completed"
            c.ended_at = c.ended_at or now
            db.commit()
            record_audit(
                db, account=None, module="campaign", action="auto_complete",
                target_type="campaign", target_id=str(c.id),
                detail={"name": c.name, "reason": reason},
            )
            try:
                from app.modules.integration.service import notify_webhooks

                notify_webhooks(db, "campaign_end",
                                {"演练名称": c.name, "结束方式": f"自动完成（{reason}）"})
            except Exception:  # 推送失败不阻断自动完成
                pass
            completed += 1
            logger.info("campaign %s auto completed (%s)", c.id, reason)
        return completed
    finally:
        db.close()
