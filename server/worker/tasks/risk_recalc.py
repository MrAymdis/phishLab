"""员工风险画像重算任务。"""
import logging

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.risk")


@celery_app.task(name="worker.tasks.risk_recalc.recalc")
def recalc():
    """TODO(一期)：按近期 track_event + 培训完成度增量重算 emp_risk_profile：

    五维：email_recognize / link_click / pwd_submit / attach_run / report_awareness
    综合分 → risk_level（0-30 低 / 31-70 中 / 71-100 高）
    """
    logger.info("TODO: risk recalc")
