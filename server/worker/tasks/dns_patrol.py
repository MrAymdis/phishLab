"""DNS 巡检任务：遍历 active 演练域名执行 SPF/DKIM/DMARC/MX 检测。

复用 channel.check_dns 口径（各 25 分，评分 0-100）；离线/解析器故障保留缓存评分；
评分较上次骤降 ≥30 分输出告警日志（webhook 推送二期接入）。
"""
import logging
from datetime import datetime

import dns.exception

from app.db.session import SessionLocal
from app.modules.channel.service import _record_exists
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.dns")

_DROP_THRESHOLD = 30


@celery_app.task(name="worker.tasks.dns_patrol.patrol")
def patrol():
    """遍历 phish_domain(status=active)：探测 DNS 记录 → 更新四状态/评分/last_check_at。"""
    from sqlalchemy import select

    from app.modules.channel.models import PhishDomain

    db = SessionLocal()
    checked = drops = 0
    try:
        domains = db.scalars(
            select(PhishDomain).where(PhishDomain.status == "active")
        ).all()
        for d in domains:
            checked += 1
            prev = d.deliver_score or 0
            try:
                spf = "ok" if _record_exists(d.domain, "TXT") else "fail"
                dkim = "ok" if _record_exists(f"{d.dkim_selector}._domainkey.{d.domain}", "TXT") else "fail"
                dmarc = "ok" if _record_exists(f"_dmarc.{d.domain}", "TXT") else "fail"
                mx = "ok" if _record_exists(d.domain, "MX") else "fail"
                score = sum(25 for s in (spf, dkim, dmarc, mx) if s == "ok")
                d.spf_status, d.dkim_status, d.dmarc_status, d.mx_status = spf, dkim, dmarc, mx
                d.deliver_score = score
                d.last_check_at = datetime.now()
            except (dns.exception.DNSException, OSError):
                # 离线/解析器故障：保留缓存评分，仅刷新检测时间
                d.last_check_at = datetime.now()
                continue
            if prev > 0 and score < prev - _DROP_THRESHOLD:
                drops += 1
                logger.warning(
                    "域名 %s 送达评分骤降：%s → %s，请检查 SPF/DKIM/DMARC/MX 配置",
                    d.domain, prev, score,
                )
        db.commit()
        if checked:
            logger.info("DNS 巡检完成：%s 个域名，%s 个评分骤降", checked, drops)
        return checked
    except Exception:
        db.rollback()
        logger.exception("DNS 巡检失败")
        raise
    finally:
        db.close()
