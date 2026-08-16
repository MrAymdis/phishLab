"""统计汇总任务：Redis 实时计数 → campaign_stat / stat_daily。"""
import logging

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.stat")


@celery_app.task(name="worker.tasks.stat_aggregate.aggregate")
def aggregate():
    """TODO(一期)：

    - 进行中演练：HGETALL cnt:{campaignId} → 回写 campaign_stat
    - 事件消费兜底：Redis Stream evt:stream 滞留检查
    - 每日任务（可用子任务）：聚合 track_event → stat_daily(platform/dept/scene/user 维度)
    """
    logger.info("TODO: stat aggregate")
