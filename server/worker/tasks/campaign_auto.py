"""演练自动调度：定时演练到点自动启动 → 到达计划结束时间自动完成。

投递完毕后演练保持 running（追踪期）：打开/点击/中招事件继续采集，
直到 ended_at（未设置时按开始时间 +7 天追踪期）才自动关闭。
幂等：仅扫描对应状态。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.campaign_auto")

_DEFAULT_TRACKING_DAYS = 7


@celery_app.task(name="worker.tasks.campaign_auto.start_scheduled")
def start_scheduled() -> int:
    """扫描到点的定时演练（scheduled + schedule_at <= now）自动启动。

    start() 内部原子认领（CAS），与手动启动并发时仅一方成功；
    已被人工启动/删除的演练抛状态错误，捕获后跳过。
    """
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign
    from app.modules.campaign.service import start

    db = SessionLocal()
    try:
        ids = db.scalars(
            select(Campaign.id).where(
                Campaign.status == "scheduled",
                Campaign.schedule_at.is_not(None),
                Campaign.schedule_at <= datetime.now(),
            )
        ).all()
        started = 0
        for cid in ids:
            try:
                start(db, None, cid)  # 系统自动启动：审计 account=None
            except Exception as e:  # 已被人工启动/删除等：跳过不中断
                db.rollback()
                logger.warning("定时演练自动启动跳过 campaign=%s：%s", cid, e)
                continue
            started += 1
            logger.info("定时演练自动启动 campaign=%s", cid)
        return started
    finally:
        db.close()


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
