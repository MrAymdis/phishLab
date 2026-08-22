"""投递引擎任务：批次派发 → 渲染 → 通道适配器发送 → 重试。

管线详见《架构设计方案》§3.2。
千人规模优化：批次共享实体（模板/落地页/域名/通道/发件人/员工/部门）一次加载，
每封渲染不再重复查询（7N 查询 → ~7 次）。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.delivery")


def _load_campaign_assets(db, campaign, target_ids: list[int]) -> dict:
    """批次共享实体一次加载：模板/落地页/域名/通道/伪装发件人 + 批次内员工与部门。"""
    from app.modules.channel.models import PhishDomain, SendChannel, SenderProfile
    from app.modules.org.models import EmpDept, EmpUser
    from app.modules.template.models import EmailTemplate, LandingPage

    tpl = db.get(EmailTemplate, campaign.template_id) if campaign.template_id else None
    lp = db.get(LandingPage, campaign.landing_page_id) if campaign.landing_page_id else None
    domain = db.get(PhishDomain, campaign.domain_id) if campaign.domain_id else None
    ch = _pick_channel(db, campaign)
    sp = db.get(SenderProfile, campaign.sender_profile_id) if campaign.sender_profile_id else None
    users = {u.id: u for u in db.scalars(
        select(EmpUser).where(EmpUser.id.in_(target_ids))).all()}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    depts = {d.id: d for d in db.scalars(
        select(EmpDept).where(EmpDept.id.in_(dept_ids))).all()} if dept_ids else {}
    return {"tpl": tpl, "lp": lp, "domain": domain, "ch": ch, "sp": sp,
            "users": users, "depts": depts}


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


def _deliver_target(db, t, campaign, assets: dict) -> bool:
    """单目标投递（批次内调用）：渲染（共享实体）→ 发送 → 回写状态与计数。

    每目标独立提交：批次中途崩溃时已发目标不重复投递（幂等兜底）。
    """
    from app.modules.campaign.models import CampaignStat
    from app.modules.campaign.render import render_campaign_email

    users = assets.get("users") or {}
    user = users.get(t.user_id)
    if user is None:
        t.send_status = "failed"
        db.commit()
        return False
    rendered = render_campaign_email(db, campaign, user, t.token, assets=assets)
    to = rendered["to"] or user.email
    subject = rendered["subject"]
    html = rendered["html"]
    sender_name = rendered["sender_name"]
    attachments = rendered.get("attachments") or []

    ch = assets.get("ch")
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
    """投递单个批次：共享实体一次加载，逐条渲染 + 发送，更新发送状态与计数。"""
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignBatch, CampaignTarget

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
        if campaign is None:
            return 0

        # 批次共享实体预加载（千人规模：7N 查询 → ~7 次）
        assets = _load_campaign_assets(db, campaign, [t.user_id for t in targets])

        sent = failed = 0
        for t in targets:
            try:
                ok = _deliver_target(db, t, campaign, assets)
            except Exception:
                db.rollback()
                logger.exception("投递异常 target=%s", t.id)
                stale = db.get(CampaignTarget, t.id)
                if stale is not None:
                    stale.send_status = "failed"
                    db.commit()
                ok = False
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
            pass  # 状态不变；completed 由到期任务处理
        db.commit()
        logger.info("deliver_batch campaign=%s batch=%s sent=%d failed=%d",
                    campaign_id, batch_no, sent, failed)
        return sent
    except Exception:
        db.rollback()
        # 批次自愈：回退 pending + 5 分钟退避，派发器重扫（代码部署故障修复后自动续投；
        # 目标行 send_status=pending 兜底，不会重复投递已发出的邮件）
        try:
            stale = db.scalar(
                select(CampaignBatch).where(
                    CampaignBatch.campaign_id == campaign_id,
                    CampaignBatch.batch_no == batch_no,
                )
            )
            if stale is not None and stale.status == "sending":
                stale.status = "pending"
                stale.plan_at = datetime.now() + timedelta(minutes=5)
                db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()


def _pick_channel(db, campaign):
    """演练指定通道（SMTP）→ 默认 SMTP 通道。"""
    from app.modules.channel.models import SendChannel

    ch = db.get(SendChannel, campaign.channel_id) if campaign.channel_id else None
    if ch and ch.type == "smtp":
        return ch
    return db.scalar(
        select(SendChannel).where(SendChannel.type == "smtp").order_by(SendChannel.is_default.desc(), SendChannel.id)
    )
