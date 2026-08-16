"""投递引擎任务：批次派发 → 渲染 → 通道适配器发送 → 重试。

管线详见《架构设计方案》§3.2。
"""
import logging

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.delivery")


@celery_app.task(name="worker.tasks.delivery.dispatch_due_batches")
def dispatch_due_batches():
    """扫描 campaign_batch 中 plan_at 到期且 status=pending 的批次，派发 deliver_batch。

    TODO(一期)：
    - 查询条件：plan_at <= now() AND status='pending'（FOR UPDATE 抢占或 CAS 更新防重复派发）
    - 校验通道当日上限 send_quota_usage，超限顺延次日
    """
    logger.info("TODO: dispatch_due_batches")
    return 0


@celery_app.task(name="worker.tasks.delivery.deliver_batch", bind=True, max_retries=3)
def deliver_batch(self, campaign_id: int, batch_no: int):
    """投递单个批次：逐条渲染模板（变量替换 + 内容随机化）→ 通道适配器发送。

    TODO(一期)：
    - campaign_target 按 batch_no 取明细；send_status pending→sent→delivered/failed
    - 发送失败指数退避：raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
    - 每封生成追踪链接 {TRACK_BASE_URL}/t/{token} 与像素 {TRACK_BASE_URL}/px/{token}.gif
    - 写 send_quota_usage / campaign_stat 计数，全部完成后 campaign.status=running
    """
    logger.info("TODO: deliver_batch campaign=%s batch=%s", campaign_id, batch_no)


@celery_app.task(name="worker.tasks.delivery.deliver_one", bind=True, max_retries=3)
def deliver_one(self, target_id: int):
    """单条投递（批次内并发单元）。"""
    logger.info("TODO: deliver_one target=%s", target_id)
