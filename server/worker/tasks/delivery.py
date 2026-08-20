"""投递引擎任务：批次派发 → 渲染 → 通道适配器发送 → 重试。

管线详见《架构设计方案》§3.2。
"""
import logging
from datetime import datetime

from sqlalchemy import select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.delivery")


def _render_email(db, target, campaign) -> dict | None:
    """渲染单封演练邮件（共享渲染逻辑 render_campaign_email）；用户不存在返回 None。"""
    from app.modules.campaign.render import render_campaign_email
    from app.modules.org.models import EmpUser

    user = db.get(EmpUser, target.user_id)
    if user is None:
        return None
    return render_campaign_email(db, campaign, user, target.token)


def _send_via_channel(db, ch, to: str, subject: str, html: str, sender_name: str,
                      attachments: list[dict] | None = None) -> bool:
    """按通道加密配置发信；成功返回 True。"""
    from app.core.security import decrypt_secret
    from app.modules.channel.service import _smtp_send

    password = ""
    if ch.smtp_password_enc:
        try:
            password = decrypt_secret(ch.smtp_password_enc)
        except Exception:
            password = ""
    cfg = {
        "smtp_host": ch.smtp_host,
        "smtp_port": ch.smtp_port,
        "smtp_encrypt": ch.smtp_encrypt,
        "smtp_username": ch.smtp_username,
        "smtp_password": password,
    }
    result = _smtp_send(ch.name, cfg, to, subject=subject, html_body=html,
                        sender_name=sender_name, attachments=attachments)
    return result["ok"]


@celery_app.task(name="worker.tasks.delivery.dispatch_due_batches")
def dispatch_due_batches():
    """扫描 plan_at 到期且 pending 的批次，派发 deliver_batch。"""
    from app.db.session import SessionLocal
    from app.modules.campaign.models import CampaignBatch

    db = SessionLocal()
    try:
        rows = db.scalars(
            select(CampaignBatch)
            .where(CampaignBatch.status == "pending", CampaignBatch.plan_at <= datetime.now())
            .order_by(CampaignBatch.plan_at)
        ).all()
        for b in rows:
            b.status = "sending"
            db.commit()
            deliver_batch.delay(b.campaign_id, b.batch_no)
        logger.info("dispatch due batches: %d", len(rows))
        return len(rows)
    finally:
        db.close()


@celery_app.task(name="worker.tasks.delivery.deliver_batch", bind=True, max_retries=3)
def deliver_batch(self, campaign_id: int, batch_no: int):
    """投递单个批次：逐条渲染 + 发送，更新发送状态与计数。"""
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignBatch, CampaignStat, CampaignTarget

    db = SessionLocal()
    try:
        batch = db.scalar(
            select(CampaignBatch).where(
                CampaignBatch.campaign_id == campaign_id,
                CampaignBatch.batch_no == batch_no,
            )
        )
        if batch is None:
            return 0
        targets = db.scalars(
            select(CampaignTarget).where(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.batch_no == batch_no,
                CampaignTarget.send_status == "pending",
            )
        ).all()
        campaign = db.get(Campaign, campaign_id)

        sent = failed = 0
        for t in targets:
            ok = deliver_one.run(t.id)  # 同步执行，保证批次内顺序与幂等
            if ok:
                sent += 1
            else:
                failed += 1

        batch.status = "done" if failed == 0 else "failed"
        batch.sent_count = sent
        batch.started_at = batch.started_at or datetime.now()
        batch.finished_at = datetime.now()
        # 投递完成后演练保持 running（追踪期开始）
        if campaign and campaign.status == "running":
            pass  # 状态不变；completed 由终止/定时任务处理
        db.commit()
        logger.info("deliver_batch campaign=%s batch=%s sent=%d failed=%d",
                    campaign_id, batch_no, sent, failed)
        return sent
    finally:
        db.close()


@celery_app.task(name="worker.tasks.delivery.deliver_one", bind=True, max_retries=3)
def deliver_one(self, target_id: int):
    """单条投递（批次内并发单元）：渲染 → 发送 → 回写状态与计数。"""
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignStat, CampaignTarget

    db = SessionLocal()
    try:
        t = db.get(CampaignTarget, target_id)
        if t is None:
            return False
        campaign = db.get(Campaign, t.campaign_id)
        if campaign is None:
            return False

        rendered = _render_email(db, t, campaign)
        if rendered is None:
            t.send_status = "failed"
            db.commit()
            return False
        to = rendered["to"]
        subject = rendered["subject"]
        html = rendered["html"]
        sender_name = rendered["sender_name"]
        attachments = rendered.get("attachments") or []

        ch = _pick_channel(db, campaign)
        if ch is None:
            t.send_status = "failed"
            db.commit()
            return False
        logger.info("投递开始 target=%s to=%s subject=%s via=%s 附件=%d",
                    t.id, to, subject, ch.name, len(attachments))
        ok = _send_via_channel(db, ch, to, subject, html, sender_name, attachments)

        t.send_status = "sent" if ok else "failed"
        t.sent_at = datetime.now() if ok else None
        if ok:
            stat = db.get(CampaignStat, campaign.id)
            if stat is None:
                stat = CampaignStat(campaign_id=campaign.id)
                db.add(stat)
            stat.delivered_cnt += 1
        db.commit()
        logger.info("投递完成 target=%s ok=%s", t.id, ok)
        return ok
    except Exception as exc:  # 发送异常指数退避重试（任务级）
        db.rollback()
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
    finally:
        db.close()


def _pick_channel(db, campaign):
    """演练指定通道（SMTP）→ 默认 SMTP 通道。"""
    from app.modules.channel.models import SendChannel

    ch = db.get(SendChannel, campaign.channel_id) if campaign.channel_id else None
    if ch and ch.type == "smtp":
        return ch
    return db.scalar(
        select(SendChannel)
        .where(SendChannel.type == "smtp")
        .order_by(SendChannel.is_default.desc(), SendChannel.id)
    )
