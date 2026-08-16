"""数据留存清理任务（合规）：到期数据自动匿名化/删除。"""
import logging

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.retention")


@celery_app.task(name="worker.tasks.retention_clean.clean")
def clean():
    """TODO(一期)：

    - 读 platform_setting.retention_days
    - track_event / open_api_log / audit_log / ai_message 超期清理或匿名化
    - MinIO 中 eml/导出文件同步清理
    """
    logger.info("TODO: retention clean")
