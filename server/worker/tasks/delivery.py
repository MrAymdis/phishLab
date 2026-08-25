"""投递引擎任务：批次派发 → 渲染 → 通道适配器发送 → 重试。

管线详见《架构设计方案》§3.2。
千人规模优化：批次共享实体（模板/落地页/域名/通道/发件人/员工/部门）一次加载，
每封渲染不再重复查询（7N 查询 → ~7 次）。
反垃圾对抗（发送行为随机化）：批次内打乱投递顺序 + 逐封随机间隔，
打破"按名单顺序瞬时连发"的规律行为指纹，降低被网关行为分析误判为群发的概率。
"""
import logging
import random
import time
from datetime import datetime, timedelta

from sqlalchemy import exists, select, update

from app.db.stat_upsert import stat_inc
from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.delivery")

# 逐封发送间隔随机抖动区间（秒）。SMTP 会话本身有网络往返，此间隔用于
# 打散"批次内瞬时连发"模式；上限 3s 避免大批次线性拖长任务时间。
_SEND_JITTER_SEC = (0.5, 3.0)


def _load_campaign_assets(db, campaign, target_ids: list[int]) -> dict:
    """批次共享实体一次加载：模板/落地页/域名/通道/伪装发件人 + 批次内员工与部门 + 附件载荷。"""
    from app.modules.campaign.models import CampaignAttachment
    from app.modules.channel.models import PhishDomain, SendChannel, SenderProfile
    from app.modules.org.models import EmpDept, EmpUser
    from app.modules.template.models import AttachmentPayload, EmailTemplate, LandingPage

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
    # 附件载荷（campaign_attachment → payload）批次共享，避免每封重复查询
    payloads = db.execute(
        select(CampaignAttachment, AttachmentPayload)
        .join(AttachmentPayload, AttachmentPayload.id == CampaignAttachment.payload_id)
        .where(CampaignAttachment.campaign_id == campaign.id)
        .order_by(CampaignAttachment.sort, CampaignAttachment.id)
    ).all()
    return {"tpl": tpl, "lp": lp, "domain": domain, "ch": ch, "sp": sp,
            "users": users, "depts": depts, "payloads": payloads}


def _check_recipient_domain(email: str, cache: dict[str, str | None]) -> str | None:
    """投递前 DNS 预检收件人域名：返回 None=可投递，否则为失败原因。

    背景：QQ 等 SMTP 服务器对收件人域名不做存在性检查（RCPT 阶段一律 250 入队），
    NXDOMAIN/无 MX 的域名会显示"假成功"后再异步退信。投递前预检让这类目标
    立即失败，避免假 sent。批次内同域名共享缓存（千人规模不会每封重复解析）。
    """
    import dns.resolver

    domain = (email or "").rsplit("@", 1)[-1].lower()
    if not domain or "." not in domain:
        return f"收件人邮箱格式无效：{email}"
    if domain in cache:
        return cache[domain]
    try:
        dns.resolver.resolve(domain, "MX")
        cache[domain] = None  # 有 MX，可投递
    except dns.resolver.NoAnswer:
        # 无 MX：按 RFC 5321 应回退 A 记录直投，但现代互联网无 MX 即不可收信
        # （A 记录几乎都是网站/CDN）；直接失败，避免假 sent
        cache[domain] = f"收件人域名无 MX 记录，无法投递邮件（{domain}）"
    except dns.resolver.NXDOMAIN:
        cache[domain] = f"收件人域名不存在（{domain}）"
    except (dns.resolver.NoNameservers, TimeoutError, OSError):
        cache[domain] = None  # DNS 服务器不可达：放行交给 SMTP 会话判定
    return cache[domain]


def _send_via_channel(db, ch, to: str, subject: str, html: str, sender_name: str,
                      attachments: list[dict] | None = None,
                      from_addr: str | None = None, reply_to: str | None = None) -> tuple[bool, str]:
    """按通道加密配置发信；返回 (成功, 失败原因)。from_addr/reply_to 为伪装发件人（From 头展示）。"""
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
                        sender_name=sender_name, from_addr=from_addr,
                        reply_to=reply_to, attachments=attachments)
    return result["ok"], result.get("message", "")


def _deliver_target(db, t, campaign, assets: dict) -> bool:
    """单目标投递（批次内调用）：渲染（共享实体）→ 发送 → 回写状态、原因与计数。

    每目标独立提交：批次中途崩溃时已发目标不重复投递（幂等兜底）。
    """
    from app.modules.campaign.models import CampaignStat
    from app.modules.campaign.render import render_campaign_email

    users = assets.get("users") or {}
    user = users.get(t.user_id)
    if user is None:
        t.send_status = "failed"
        t.fail_reason = f"目标员工不存在（user_id={t.user_id}）"
        db.commit()
        return False
    rendered = render_campaign_email(db, campaign, user, t.token, assets=assets, target=t)
    to = rendered["to"] or user.email
    subject = rendered["subject"]
    html = rendered["html"]
    sender_name = rendered["sender_name"]
    from_addr = rendered.get("from_addr")
    reply_to = rendered.get("reply_to")
    attachments = rendered.get("attachments") or []

    ch = assets.get("ch")
    if ch is None:
        t.send_status = "failed"
        t.fail_reason = "无可用 SMTP 发送通道"
        db.commit()
        return False
    # DNS 预检收件人域名：NXDOMAIN/无 MX 立即失败（QQ 等对域名不检查，会假 sent 后退信）
    mx_cache = assets.get("mx_cache")
    if mx_cache is not None:
        domain_err = _check_recipient_domain(to, mx_cache)
        if domain_err:
            t.send_status = "failed"
            t.fail_reason = domain_err[:500]
            t.sent_at = None
            db.commit()
            logger.info("投递预检失败 target=%s to=%s：%s", t.id, to, domain_err)
            return False
    logger.info("投递开始 target=%s to=%s subject=%s via=%s from=%s 附件=%d",
                t.id, to, subject, ch.name, from_addr or ch.smtp_username, len(attachments))
    ok, reason = _send_via_channel(db, ch, to, subject, html, sender_name, attachments,
                                   from_addr, reply_to)

    t.send_status = "sent" if ok else "failed"
    if ok:
        t.fail_reason = None
    else:
        t.fail_reason = (reason or "发送失败")[:500]
    t.sent_at = datetime.now() if ok else None
    if ok:
        # 原子累加：并发批次投递下避免读-改-写竞态（lost update）
        stat_inc(db, campaign.id, delivered_cnt=1)
    db.commit()
    logger.info("投递完成 target=%s ok=%s", t.id, ok)
    return ok


@celery_app.task(name="worker.tasks.delivery.dispatch_due_batches")
def dispatch_due_batches():
    """扫描 plan_at 到期且 pending 的批次，派发 deliver_batch。

    只派发「运行中演练」的批次：暂停/终止后批次不再投递（resume 后由本扫描恢复）。
    """
    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignBatch

    db = SessionLocal()
    try:
        rows = db.scalars(
            select(CampaignBatch)
            .join(Campaign, Campaign.id == CampaignBatch.campaign_id)
            .where(
                CampaignBatch.status == "pending",
                CampaignBatch.plan_at <= datetime.now(),
                Campaign.status.in_(("sending", "running")),
            )
            .order_by(CampaignBatch.plan_at)
        ).all()
        for b in rows:
            # 原子认领：beat 兜底扫描与启动时手动派发并发时仅一方成功，
            # 防止同一批次被派发两次（否则两个 deliver_batch 重复发信）
            claimed = db.execute(
                update(CampaignBatch)
                .where(CampaignBatch.id == b.id, CampaignBatch.status == "pending")
                .values(status="sending")
            )
            db.commit()
            if claimed.rowcount == 0:
                continue  # 已被其他派发器认领
            try:
                deliver_batch.delay(b.campaign_id, b.batch_no)
            except Exception:
                # 派发失败（如 Redis 不可用）回退 pending，等下次扫描重试，避免僵尸 sending 批次
                logger.exception("批次派发失败 campaign=%s batch=%s", b.campaign_id, b.batch_no)
                db.execute(
                    update(CampaignBatch)
                    .where(CampaignBatch.id == b.id, CampaignBatch.status == "sending")
                    .values(status="pending")
                )
                db.commit()
        # 投递完毕的演练转 running（追踪期）：sending + 无 pending/sending 批次即视为
        # 投递结束（done/failed 均结束——失败目标保留表内供处置）。幂等 UPDATE：
        # 多派发器/并发下即使同轮执行也只一方命中 WHERE status=sending。
        transferred = db.execute(
            update(Campaign)
            .where(
                Campaign.status == "sending",
                ~exists(
                    select(CampaignBatch.id).where(
                        CampaignBatch.campaign_id == Campaign.id,
                        CampaignBatch.status.in_(("pending", "sending")),
                    )
                ),
            )
            .values(status="running")
        )
        db.commit()
        if transferred.rowcount:
            logger.info("campaign sending→running（投递完毕进入追踪期）: %d", transferred.rowcount)
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
        if batch is None or batch.status not in ("pending", "sending"):
            return 0  # 批次不存在或已完成：防重复执行
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return 0
        if campaign.status not in ("sending", "running"):
            # 演练已暂停/终止：批次回退 pending（resume 后由派发器恢复投递），不真实发信
            batch.status = "pending"
            db.commit()
            return 0
        targets = db.scalars(
            select(CampaignTarget).where(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.batch_no == batch_no,
                CampaignTarget.send_status == "pending",
            )
        ).all()
        # 反垃圾对抗：打乱投递顺序——目标默认按主键（名单导入顺序）排列，
        # 同一名单每场演练都是同一规律序列，易被行为分析识别为批量群发。
        # 仅影响发送顺序，不改变批次归属/幂等键（batch_no 不变，重试按
        # send_status=pending 过滤，已发目标不会重复投递）。
        random.shuffle(targets)

        # 批次共享实体预加载（千人规模：7N 查询 → ~7 次）
        assets = _load_campaign_assets(db, campaign, [t.user_id for t in targets])
        # 收件人域名 DNS 预检缓存（域名 → None=可投递 / 失败原因），批次内共享
        assets["mx_cache"] = {}

        sent = failed = 0
        for idx, t in enumerate(targets):
            if idx > 0:
                time.sleep(random.uniform(*_SEND_JITTER_SEC))
            try:
                ok = _deliver_target(db, t, campaign, assets)
            except Exception as e:
                db.rollback()
                logger.exception("投递异常 target=%s", t.id)
                stale = db.get(CampaignTarget, t.id)
                if stale is not None:
                    stale.send_status = "failed"
                    stale.fail_reason = f"投递异常：{str(e)}"[:500]
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
        # 批次完成；演练 sending→running（进入追踪期）由派发器扫描「无待投批次」时转换；
        # completed 由到期任务处理
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
