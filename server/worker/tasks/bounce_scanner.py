"""退信回扫：IMAP 抓取发送账号退信 → 解析失败收件人 → campaign_target sent→bounced。

SMTP 协议只保证"服务器接受"（250 即返回成功），对方异步拒收（账号不存在/邮箱满/被拒收）
通过退信（bounce）返回发送账号。本任务定时回扫各 SMTP 通道的收件箱，
把"已发送但实际未达"的目标纠正为 bounced 并记录退信原因，投递失败列表随之可见。

幂等设计：
- 仅处理 send_status == 'sent' 的目标（failed/bounced 不再触碰）；
- 已扫描的退信标记 \\Seen，搜索仅针对 UNSEEN，同一退信不会重复处理；
- 单通道异常（IMAP 登录失败等）跳过不中断其他通道。

安全：通道密码在内存中解密（AES-GCM），不落盘、不打印。
"""
import email
import html
import imaplib
import logging
import re

import redis
from email.header import decode_header, make_header
from sqlalchemy import func, select

from worker.celery_app import celery_app

logger = logging.getLogger("phishlab.bounce")


def _dec(v) -> str:
    """解码 MIME 编码的邮件头（=?utf-8?B?...?= → 可读文本）。"""
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return str(v or "")

# 常见 IMAP 主机映射：smtp_host → imap_host（QQ/163/126/gmail 均为同域替换）
_IMAP_HOSTS = {
    "smtp.qq.com": "imap.qq.com",
    "smtp.163.com": "imap.163.com",
    "smtp.126.com": "imap.126.com",
    "smtp.189.cn": "imap.189.cn",
    "smtp.sina.com": "imap.sina.com",
    "smtp.gmail.com": "imap.gmail.com",
    "smtp.mxhichina.com": "imap.mxhichina.com",
    "smtp.exmail.qq.com": "imap.exmail.qq.com",
}

# 退信识别：发件人或主题命中即视为退信
_FROM_RE = re.compile(r"mailer[-_ ]?daemon|postmaster|delivery failure", re.I)
_SUBJECT_RE = re.compile(
    r"undelivered mail|mail delivery (failed|failure)|delivery status notification|"
    r"failure notice|delivery failure|returned mail|无法投递|退信|投递失败|邮件被退回|"
    r"message could not be delivered", re.I,
)
# 失败收件人：DSN 标准头
_RECIPIENT_HEADERS = ("x-failed-recipients", "final-recipient", "original-recipient")
# 退信正文中的 SMTP 拒绝原因（550/552/553/554/551/450 后跟文本）
_REASON_RE = re.compile(
    r"(?:550|551|552|553|554|450|452)[:\s]*([^\r\n]+)", re.I,
)
# 正文兜底：常见无法投递短语
_MAILBOX_RE = re.compile(
    r"(no such user|user unknown|invalid (?:recipient|address)|mailbox (?:unavailable|not found)|"
    r"recipient may contain a non-existent account|address rejected|does not exist)", re.I,
)


def _imap_host(smtp_host: str) -> str:
    """smtp_host → imap_host；映射表缺失时按 smtp.→imap. 规则兜底。"""
    host = (smtp_host or "").strip().lower()
    if host in _IMAP_HOSTS:
        return _IMAP_HOSTS[host]
    if host.startswith("smtp."):
        return "imap." + host[len("smtp."):]
    return host or ""


def _clean_email(raw: str) -> str:
    """清洗退信头里的收件人：去标签/引号/空白，取邮箱部分。"""
    m = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", raw or "")
    return m.group(0).lower() if m else ""


def _extract_recipients(msg) -> list[str]:
    """从退信邮件中提取失败收件人列表。

    优先级：DSN 标准头（X-Failed-Recipients/Final-Recipient）→
    "无法发送到 xx@yy" 标记（QQ/163 退信正文）→ 正文裸邮箱兜底。
    过滤收件箱账号自身与 QQ 系统代发地址（tencent_<md5>@qq.com），避免误归属。
    """
    self_addr = (msg.get("To") or "").lower()
    sys_addr_re = re.compile(r"^tencent_[a-f0-9]{32}@qq\.com$")

    def _valid(em: str) -> bool:
        return bool(em) and em not in found and em != self_addr and not sys_addr_re.match(em)

    found: list[str] = []
    for part in msg.walk():
        for hdr in _RECIPIENT_HEADERS:
            val = _dec(part.get(hdr))
            if val:
                # Final-Recipient: rfc822;xx@yy 形态
                cleaned = _clean_email(val.split(";")[-1] if ";" in val else val)
                if _valid(cleaned):
                    found.append(cleaned)
    if found:
        return found
    # 正文兜底：优先 "无法发送到 xxx" 标记，其次裸邮箱（QQ 退信无尖括号）
    marked_re = re.compile(
        r"(?:无法发送到|不能发送到|unable to deliver to|failed to deliver to|"
        r"recipient (?:address )?(?:is|was) (?:not|unavailable|unknown))"
        r"\s*[:(]?\s*([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})", re.I,
    )
    for part in msg.walk():
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        for m in marked_re.finditer(text):
            em = m.group(1).lower()
            if _valid(em):
                found.append(em)
        if found:
            return found
        for m in re.finditer(r"([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})", text):
            em = m.group(1).lower()
            if _valid(em):
                found.append(em)
    return found[:10]


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _extract_reason(msg) -> str:
    """提取退信原因：正文中的 SMTP 拒绝码文本或无法投递短语。"""
    for part in msg.walk():
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        if part.get_content_type() == "text/html":
            text = _HTML_TAG_RE.sub(" ", text)  # 剥 HTML 标签，避免 </td> 等残留
        m = _REASON_RE.search(text)
        if m:
            return html.unescape(m.group(1).strip()).replace("\xa0", " ")[:200]
        m = _MAILBOX_RE.search(text)
        if m:
            return html.unescape(m.group(0)).replace("\xa0", " ")[:200]
    return "收件方拒绝接收（详见退信邮件）"


def _bounce_key(msg) -> str:
    """退信唯一键：Message-ID，缺失时用 From+Subject+Date 哈希兜底（防重复处理）。"""
    mid = (msg.get("Message-ID") or "").strip()
    if mid:
        return mid
    import hashlib

    raw = f"{msg.get('From')}|{msg.get('Subject')}|{msg.get('Date')}"
    return "noid:" + hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()


def _scan_channel(db, ch) -> int:
    """单通道回扫：返回纠正为 bounced 的目标数。IMAP 异常抛出由外层捕获。"""
    import hashlib

    from app.core.security import decrypt_secret
    from app.core.config import settings

    host = _imap_host(ch.smtp_host or "")
    username = (ch.smtp_username or "").strip()
    if not host or not username or not ch.smtp_password_enc:
        logger.info("通道 %s 无 IMAP 能力（缺 host/账号/密码），跳过", ch.name)
        return 0
    password = decrypt_secret(ch.smtp_password_enc)
    if not password:
        logger.info("通道 %s 密码解密失败，跳过", ch.name)
        return 0

    fixed = 0
    try:
        conn = imaplib.IMAP4_SSL(host, 993, timeout=15)
    except Exception as err:
        # 演示/内网通道无公网 IMAP 或 DNS 不可达：跳过该通道，不视为异常
        logger.info("通道 %s 无法连接 IMAP %s：%s，跳过", ch.name, host, err)
        return 0
    try:
        conn.login(username, password)
        # QQ/163 的 imap 默认搜索范围是"收件箱"，退信投递到收件箱；
        # 扫全部（含已读）而非 UNSEEN：用户手动看过的退信也要能纠正，
        # 幂等靠 Redis Message-ID 去重，不依赖邮件的已读标记。
        conn.select("INBOX")
        typ, data = conn.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            logger.info("通道 %s 收件箱为空", ch.name)
            return 0
        ids = data[0].split()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        seen_key = f"bounce_seen:{ch.id}"
        logger.info("通道 %s 扫描收件箱 %d 封邮件", ch.name, len(ids))
        for num in ids:
            try:
                typ, msg_data = conn.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                from_hdr = _dec(msg.get("From"))
                subj = _dec(msg.get("Subject"))
                if not (_FROM_RE.search(from_hdr) or _SUBJECT_RE.search(subj)):
                    continue  # 非退信
                key = _bounce_key(msg)
                if r.sismember(seen_key, key):
                    continue  # 已处理过
                recipients = _extract_recipients(msg)
                if not recipients:
                    logger.info("退信无法解析收件人 subject=%s", subj[:80])
                    r.sadd(seen_key, key)
                    r.expire(seen_key, 7 * 86400)
                    continue
                reason = _extract_reason(msg)
                fixed += _mark_bounced(db, recipients, reason)
                r.sadd(seen_key, key)
                r.expire(seen_key, 7 * 86400)
            except Exception:
                logger.exception("解析退信异常 msg=%s", num)
        return fixed
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _mark_bounced(db, recipients: list[str], reason: str) -> int:
    """按收件人邮箱匹配所有 sent 目标 → bounced + 原因 + bounce 事件。

    同时原子回减 campaign_stat.delivered_cnt（投递时 sent 已累加，退信纠正后
    冗余计数保持与"实时 sent 数"一致，列表页/详情页口径统一）。
    """
    from sqlalchemy.dialects.mysql import insert

    from app.modules.campaign.models import CampaignStat, CampaignTarget
    from app.modules.org.models import EmpUser
    from app.modules.tracking.stream import push_event

    fixed = 0
    for email_addr in recipients:
        targets = db.scalars(
            select(CampaignTarget)
            .join(EmpUser, EmpUser.id == CampaignTarget.user_id)
            .where(
                EmpUser.email == email_addr,
                CampaignTarget.send_status == "sent",
            )
        ).all()
        for t in targets:
            t.send_status = "bounced"
            t.fail_reason = f"退信：{reason}"[:500]
            # 原子回减投递成功计数（纠正目标数）
            stmt = insert(CampaignStat).values(campaign_id=t.campaign_id, delivered_cnt=0)
            db.execute(stmt.on_duplicate_key_update(
                delivered_cnt=func.greatest(CampaignStat.delivered_cnt - 1, 0)))
            try:
                push_event(token=t.token, event_type="bounce",
                           ip="", ua="", detail={"reason": reason})
            except Exception:
                logger.exception("bounce 事件推送失败 target=%s", t.id)
            fixed += 1
            logger.info("退信纠正 target=%s email=%s → bounced（%s）", t.id, email_addr, reason[:80])
    if fixed:
        db.commit()
    return fixed


@celery_app.task(name="worker.tasks.bounce_scanner.scan_bounces")
def scan_bounces():
    """遍历全部 SMTP 通道回扫退信；单通道异常不中断。"""
    from app.db.session import SessionLocal
    from app.modules.channel.models import SendChannel

    db = SessionLocal()
    try:
        channels = db.scalars(
            select(SendChannel).where(SendChannel.type == "smtp")
        ).all()
        total = 0
        for ch in channels:
            try:
                total += _scan_channel(db, ch)
            except Exception:
                logger.exception("通道 %s 退信回扫失败", ch.name)
        logger.info("退信回扫完成：%d 个通道，纠正 %d 个目标", len(channels), total)
        return total
    finally:
        db.close()
