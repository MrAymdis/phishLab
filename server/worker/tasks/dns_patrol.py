"""DNS 巡检任务：dnspython 探测 SPF/DKIM/DMARC/MX → 送达评分 + 修复指引。"""
import logging

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.dns")


@celery_app.task(name="worker.tasks.dns_patrol.patrol")
def patrol():
    """遍历 phish_domain(status=active)：

    TODO(一期)：
    - SPF: TXT 查询含 v=spf1；DKIM: {selector}._domainkey TXT；DMARC: _dmarc TXT；MX 记录
    - deliver_score = SPF30 + DKIM30 + DMARC20 + MX10 + 黑名单查询10
    - 生成 repair_tips 文案，更新 last_check_at；评分骤降时告警（webhook）
    """
    logger.info("TODO: dns patrol")
