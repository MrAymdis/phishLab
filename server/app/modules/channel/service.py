"""发送配置服务：通道连通性探测、演练域名 DNS 巡检、伪装发件人。"""
import socket
import time
from datetime import datetime
from urllib.parse import urlparse

import dns.exception
import dns.resolver
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.errors import BizError, ErrorCode
from app.core.security import encrypt_secret

from app.modules.campaign.models import Campaign, CampaignTarget

from .models import PhishDomain, SendChannel, SenderProfile

_TYPE_LABELS = {"smtp": "SMTP", "ews": "Exchange EWS", "sms": "短信机"}
# 列表卡片强调色按 (type, 序号) 轮换
_ACCENTS = {"smtp": ["blue", "teal"], "ews": ["purple"], "sms": ["orange", "green", "red"]}
_STATUS_TEXT = {"ok": "OK", "unknown": "WARN", "fail": "FAIL"}


# ---------- 通道 ----------

def _tcp_probe(host: str | None, port: int | None) -> dict:
    """TCP 连通探测；返回 {"ok", "score", "latency_ms", "message"}。"""
    if not host or not port:
        return {"ok": False, "score": 40, "latency_ms": None, "message": "未配置服务器地址"}
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=5):
            latency = int((time.perf_counter() - t0) * 1000)
        return {"ok": True, "score": 90, "latency_ms": latency, "message": f"TCP 连接成功，延迟 {latency}ms"}
    except OSError as err:
        return {"ok": False, "score": 40, "latency_ms": None, "message": f"连接失败：{err}"}


def _resolve_probe_target(ch_type: str, cfg: dict) -> tuple[str | None, int | None]:
    """按类型解析探测目标：smtp 用 host/port；ews 取 url 的 host 走 443。"""
    if ch_type == "smtp":
        port = cfg.get("smtp_port") or (465 if cfg.get("smtp_encryption") == "ssl" else 587)
        return cfg.get("smtp_host"), int(port)
    if ch_type == "ews":
        url = cfg.get("ews_url")
        return (urlparse(url).hostname if url else None), 443
    return None, None


def channel_overview(db, account) -> dict:
    """发送配置概览：本月发送总量（campaign_target 真实聚合）。

    口径：本月内已实际发送的目标行（sent/delivered/bounced/failed 均计入，
    只有 pending 未发出），以 sent_at 落点归月。
    """
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.scalar(
        select(func.count())
        .select_from(CampaignTarget)
        .where(
            CampaignTarget.send_status.in_(["sent", "delivered", "bounced", "failed"]),
            CampaignTarget.sent_at >= month_start,
        )
    ) or 0
    days = datetime.now().day
    return {"monthly_sent": total, "daily_avg": round(total / days) if days else 0}


def list_channels(db, account) -> list[dict]:
    """通道列表；密码/密钥类字段永不回显。"""
    rows = db.scalars(select(SendChannel).order_by(SendChannel.id)).all()
    idx: dict[str, int] = {}
    result = []
    for ch in rows:
        palette = _ACCENTS.get(ch.type, ["blue"])
        accent = palette[idx.get(ch.type, 0) % len(palette)]
        idx[ch.type] = idx.get(ch.type, 0) + 1
        last = ch.last_test_result or {}
        result.append(
            {
                "id": ch.id,
                "name": ch.name,
                "type": ch.type,
                "type_label": _TYPE_LABELS.get(ch.type, ch.type),
                "accent": accent,
                "status": "ok" if ch.status == "normal" else "error",
                "score": int(last.get("score", 0)),
                "last_test": ch.last_test_at.strftime("%Y-%m-%d %H:%M") if ch.last_test_at else "从未测试",
                "server": ch.smtp_host,
                "port": ch.smtp_port,
                "ssl": ch.smtp_encrypt == "ssl",
                "url": ch.ews_url,
                "auth_mode": (ch.ews_auth_mode or "")
                + (" · OAuth2 · Azure AD" if ch.ews_auth_mode == "oauth2" else ""),
                "provider": ch.sms_provider,
                "signature": ch.sms_sign,
                "daily_limit": ch.daily_limit,
                "is_default": bool(ch.is_default),
                # 编辑回填用（非敏感字段；密码/密钥类只回显是否已设置）
                "smtp_user": ch.smtp_username,
                "smtp_encryption": ch.smtp_encrypt or "",
                "ews_user": ch.ews_username,
                "ews_auth_mode_raw": ch.ews_auth_mode,
                "oauth_client_id": ch.oauth_client_id,
                "oauth_tenant_id": ch.oauth_tenant_id,
                "sms_url": ch.sms_api_url,
                "sms_key": ch.sms_key,
                "sms_template_id": ch.sms_template_id,
                "sms_port_dev": ch.serial_port,
                "sms_baudrate": ch.baud_rate,
                "sms_sim": ch.sim_number,
                "has_smtp_pass": bool(ch.smtp_password_enc),
                "has_ews_pass": bool(ch.ews_password_enc),
                "has_client_secret": bool(ch.oauth_client_secret_enc),
                "has_sms_secret": bool(ch.sms_secret_enc),
            }
        )
    return result


def _channel_kw_from_payload(payload: dict) -> dict:
    """弹窗 payload → 模型列映射；敏感字段 AES-GCM 加密（空值返回 None 表示不设置）。"""
    ch_type = payload.get("type") or ""
    cfg = payload.get("config") or {}
    if ch_type not in ("smtp", "ews", "sms"):
        raise BizError(ErrorCode.PARAM_INVALID, f"不支持的通道类型：{ch_type}")

    def _enc(v: str | None) -> bytes | None:
        return encrypt_secret(v) if v else None

    kw: dict = {
        "name": payload["name"],
        "type": ch_type,
        "daily_limit": int(payload.get("daily_limit") or 5000),
        "is_default": 1 if payload.get("is_default") else 0,
    }
    if ch_type == "smtp":
        kw.update(
            smtp_host=cfg.get("smtp_host"),
            smtp_port=int(cfg["smtp_port"]) if cfg.get("smtp_port") else None,
            smtp_encrypt=(cfg.get("smtp_encryption") or "").lower() or None,
            smtp_username=cfg.get("smtp_user"),
            smtp_password_enc=_enc(cfg.get("smtp_pass")),
        )
    elif ch_type == "ews":
        kw.update(
            ews_url=cfg.get("ews_url"),
            ews_username=cfg.get("ews_user"),
            ews_password_enc=_enc(cfg.get("ews_pass")),
            ews_auth_mode=cfg.get("ews_auth_mode"),
            oauth_client_id=cfg.get("ews_client_id"),
            oauth_client_secret_enc=_enc(cfg.get("ews_client_secret")),
            oauth_tenant_id=cfg.get("ews_tenant_id"),
        )
    else:  # sms
        kw.update(
            sms_provider=cfg.get("sms_provider"),
            sms_api_url=cfg.get("sms_url"),
            sms_sign=cfg.get("sms_signature"),
            sms_key=cfg.get("sms_api_key"),
            sms_secret_enc=_enc(cfg.get("sms_api_secret")),
            sms_template_id=cfg.get("sms_template_id"),
            serial_port=cfg.get("sms_port_dev"),
            baud_rate=int(cfg["sms_baudrate"]) if cfg.get("sms_baudrate") else None,
            sim_number=cfg.get("sms_sim"),
        )
    return kw


def _probe_result(ch_type: str, cfg: dict) -> tuple[dict, str]:
    """保存前连通测试；SMS 通道仅登记，发送能力待真机验证。"""
    if ch_type == "sms":
        return {"ok": True, "score": 80, "latency_ms": None, "message": "SMS 通道已保存，发送能力待真机验证"}, "normal"
    result = _tcp_probe(*_resolve_probe_target(ch_type, cfg))
    return result, "normal" if result["ok"] else "abnormal"


def create_channel(db, account, payload: dict) -> int:
    """新建通道：敏感字段 AES-GCM 加密入库；保存前做 TCP 连通探测。"""
    kw = _channel_kw_from_payload(payload)
    result, status = _probe_result(kw["type"], payload.get("config") or {})

    ch = SendChannel(**kw, status=status, last_test_result=result, last_test_at=datetime.now())
    db.add(ch)
    db.commit()
    db.refresh(ch)
    record_audit(
        db, account=account, module="channel", action="create_channel",
        target_type="send_channel", target_id=ch.id, detail={"type": kw["type"]},
    )
    return ch.id


def update_channel(db, account, channel_id: int, payload: dict) -> None:
    """更新通道：敏感字段留空表示沿用已有密文；保存前重做连通探测。"""
    ch = db.get(SendChannel, channel_id)
    if ch is None:
        raise BizError(ErrorCode.NOT_FOUND)

    kw = _channel_kw_from_payload(payload)
    ch_type = kw.pop("type")
    # 敏感字段留空 → 沿用已有密文，不覆盖
    for col in ("smtp_password_enc", "ews_password_enc", "oauth_client_secret_enc", "sms_secret_enc"):
        if kw.get(col) is None:
            kw.pop(col, None)
    for k, v in kw.items():
        setattr(ch, k, v)
    # 类型变更时清空其他类型的遗留字段
    if ch.type != ch_type:
        for col in ("smtp_host", "smtp_port", "smtp_encrypt", "smtp_username",
                    "ews_url", "ews_username", "ews_auth_mode", "oauth_client_id", "oauth_tenant_id",
                    "sms_provider", "sms_api_url", "sms_sign", "sms_key",
                    "sms_template_id", "serial_port", "baud_rate", "sim_number"):
            if col not in kw:
                setattr(ch, col, None)
        ch.type = ch_type

    result, status = _probe_result(ch.type, payload.get("config") or {})
    ch.last_test_result = result
    ch.last_test_at = datetime.now()
    # 编辑保存不翻转已有状态：探测成功 → normal；失败 → 保留原状态（明确测连通请用「连通测试」按钮）
    if status == "normal" and ch.status != "disabled":
        ch.status = "normal"
    db.commit()
    record_audit(
        db, account=account, module="channel", action="update_channel",
        target_type="send_channel", target_id=ch.id, detail={"type": ch.type},
    )


def delete_channel(db, account, channel_id: int) -> None:
    """删除通道：历史演练仅存 channel_id 引用（无外键约束），物理删除 + 审计。"""
    ch = db.get(SendChannel, channel_id)
    if ch is None:
        raise BizError(ErrorCode.NOT_FOUND)
    name, ch_type = ch.name, ch.type
    db.delete(ch)
    db.commit()
    record_audit(
        db, account=account, module="channel", action="delete_channel",
        target_type="send_channel", target_id=channel_id, detail={"name": name, "type": ch_type},
    )


def _spoof_reject_note(username: str, from_addr: str | None) -> str:
    """伪装 From 域与发送账号域不一致时的拒收说明（公共邮箱反垃圾机制，非通道故障）。"""
    acct_domain = username.split("@")[-1].lower() if "@" in username else ""
    from_domain = (from_addr or "").split("@")[-1].lower() if from_addr and "@" in from_addr else ""
    if from_addr and acct_domain and from_domain != acct_domain:
        return "（From 为伪装地址，与发送账号域名不一致；公共邮箱会按反垃圾策略拒收，请用企业内网邮箱收件验证）"
    return ""


def _smtp_send(
    name: str, cfg: dict, to: str,
    subject: str | None = None, html_body: str | None = None,
    sender_name: str | None = None, from_addr: str | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    """纯发信：按 SMTP 配置真实发送一封测试邮件（不触碰数据库）。

    subject/html_body 传入时按指定内容发送（向导预览真实演练邮件样式），
    否则发送通用通道测试邮件。
    attachments: [{filename, content(bytes), content_id}] —
    作为邮件附件发送，同时以 Content-ID 供正文 <img src="cid:..."> 内嵌引用。
    """
    import smtplib
    from email.mime.image import MIMEImage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr

    host = cfg.get("smtp_host")
    if not host:
        raise BizError(ErrorCode.PARAM_INVALID, "通道未配置 SMTP 服务器地址")
    username = cfg.get("smtp_username") or cfg.get("smtp_user")
    if not username:
        raise BizError(ErrorCode.PARAM_INVALID, "通道未配置发送账号")
    # 公共邮箱自投递（发件账号 == 收件人）可能被静默丢弃：SMTP 返回 250 但邮件不达
    if username.lower() == (to or "").lower():
        import logging as _logging

        _logging.getLogger("phishlab.delivery").warning(
            "自发自收邮件：发件账号与收件人相同（%s），公共邮箱可能静默丢弃（SMTP 仍返回 250）", to,
        )
    # 兼容两种键名：库表列名 smtp_username/smtp_password/smtp_encrypt 与前端表单键 smtp_user/smtp_pass/smtp_encryption
    password = cfg.get("smtp_password") or cfg.get("smtp_pass") or ""
    encrypt = (cfg.get("smtp_encrypt") or cfg.get("smtp_encryption") or "").lower()
    port = cfg.get("smtp_port") or (465 if encrypt == "ssl" else 587)

    if html_body is not None:
        subject = subject or "【PhishLab】演练邮件预览"
    else:
        html_body = (
            f"这是一封来自 PhishLab 的测试邮件。\n\n发送通道：{name}\n"
            f"SMTP 服务器：{host}:{port}\n发送时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
            "收到此邮件表示该通道可以正常发信。"
        )
        subject = "【PhishLab】发送通道测试邮件"

    if attachments:
        # multipart/related：正文 HTML + 内嵌附件（Content-ID 引用 + 可下载）
        msg = MIMEMultipart("related")
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        for att in attachments:
            image = MIMEImage(att["content"], _subtype="png", name=att.get("filename", "image.png"))
            image.add_header("Content-ID", f"<{att.get('content_id', '')}>")
            image.add_header("Content-Disposition", "attachment", filename=att.get("filename", "image.png"))
            msg.attach(image)
    else:
        msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    # from_addr 为伪装发件人地址（仅影响收件端展示的 From 头，信封仍用发送账号保证送达）
    msg["From"] = formataddr((sender_name or name, from_addr or username))
    msg["To"] = to

    t0 = time.perf_counter()
    server = None
    try:
        if encrypt == "ssl":
            server = smtplib.SMTP_SSL(host, int(port), timeout=10)
        else:
            server = smtplib.SMTP(host, int(port), timeout=10)
            if encrypt == "starttls":
                server.starttls()
        # 记录完整 SMTP 会话（reply: 250 ... 即服务器接受响应），供投递追踪排障
        server.set_debuglevel(1)
        if password:
            server.login(username, password)
        refused = server.sendmail(username, [to], msg.as_string())
        latency = int((time.perf_counter() - t0) * 1000)
        if refused:
            return {"ok": False, "score": 40, "latency_ms": latency,
                    "message": f"发送被拒收：{refused}" + _spoof_reject_note(username, from_addr)}
        return {"ok": True, "score": 100, "latency_ms": latency,
                "message": f"邮件已发送至 {to}（{latency}ms）"}
    except smtplib.SMTPAuthenticationError:
        return {"ok": False, "score": 40, "latency_ms": None,
                "message": "认证失败：请使用 SMTP 授权码（QQ/163 邮箱需在设置中生成授权码，不能用登录密码）"}
    except (TimeoutError, socket.timeout):
        return {"ok": False, "score": 40, "latency_ms": None,
                "message": f"连接超时：端口与加密方式可能不匹配（465 端口需 SSL/TLS，587 端口需 STARTTLS），当前为 {host}:{port} + {encrypt or '无加密'}"}
    except smtplib.SMTPServerDisconnected as err:
        return {"ok": False, "score": 40, "latency_ms": None,
                "message": f"服务器断开连接：{err}（可能是端口/加密方式不匹配）"}
    except (smtplib.SMTPException, OSError) as err:
        return {"ok": False, "score": 40, "latency_ms": None,
                "message": f"发送失败：{err}" + _spoof_reject_note(username, from_addr)}
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def send_test_email(db, account, channel_id: int, to: str) -> dict:
    """通过已保存的 SMTP 通道真实发送测试邮件，结果回写最近测试。"""
    from app.core.security import decrypt_secret

    ch = db.get(SendChannel, channel_id)
    if ch is None:
        raise BizError(ErrorCode.NOT_FOUND)
    if ch.type != "smtp":
        raise BizError(ErrorCode.PARAM_INVALID, "仅 SMTP 通道支持测试邮件发送")

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
    result = _smtp_send(ch.name, cfg, to)

    # 真实发信验证比 TCP 探测更强，回写最近测试结果
    ch.last_test_result = result
    ch.last_test_at = datetime.now()
    if ch.status != "disabled":
        ch.status = "normal" if result["ok"] else ch.status
    db.commit()
    record_audit(
        db, account=account, module="channel", action="send_test_email",
        target_type="send_channel", target_id=ch.id, detail={"to": to, "ok": result["ok"]},
    )
    return result


def send_test_email_draft(db, account, payload: dict) -> dict:
    """用弹窗中尚未保存的配置发送测试邮件（不落库、不影响通道记录）。"""
    ch_type = payload.get("type") or ""
    if ch_type != "smtp":
        raise BizError(ErrorCode.PARAM_INVALID, "仅 SMTP 通道支持测试邮件发送")
    cfg = payload.get("config") or {}
    name = payload.get("name") or "未保存的通道"
    result = _smtp_send(name, cfg, payload.get("to") or "")
    record_audit(
        db, account=account, module="channel", action="send_test_email_draft",
        target_type="send_channel", target_id=None,
        detail={"name": name, "to": payload.get("to"), "ok": result["ok"]},
    )
    return result


def send_test_email_with_content(db, account, channel_id: int, payload: dict) -> dict:
    """演练向导预览发送：按所选邮件模板 + 落地页 + 伪装发件人发送真实样式测试邮件。

    模板变量替换为演示值：{{.FirstName}}→测试收件人、{{.ResetURL}}→落地页链接等。
    """
    from app.core.config import settings
    from app.core.security import decrypt_secret
    from app.modules.template.models import EmailTemplate, LandingPage

    ch = db.get(SendChannel, channel_id)
    if ch is None:
        raise BizError(ErrorCode.NOT_FOUND)
    if ch.type != "smtp":
        raise BizError(ErrorCode.PARAM_INVALID, "仅 SMTP 通道支持测试邮件发送")

    to = payload.get("to") or ""
    tpl = db.get(EmailTemplate, payload["template_id"]) if payload.get("template_id") else None
    lp = db.get(LandingPage, payload["landing_page_id"]) if payload.get("landing_page_id") else None
    # 链接域名优先用向导选择的欺骗性域名（与真实演练邮件一致）；未选时退回独立落地页域名。
    # 演示环境：http + 落地页端口直连（开发机 hosts 映射演练域名后点击即可打开仿冒登录页）；
    # 生产部署：演练域名 DNS 指向落地页服务并配置 TLS，链接为 https://{domain}/p/{slug}。
    spoof_domain = (payload.get("domain") or "").strip().rstrip("/")
    if spoof_domain:
        landing_url = f"http://{spoof_domain}:{settings.landing_port}/p/{lp.slug}" if lp else ""
    else:
        landing_url = f"{settings.landing_base_url.rstrip('/')}/p/{lp.slug}" if lp else ""

    # 变量替换（演示值；真实演练按目标员工档案逐人渲染）
    var_map = {
        "{{.FirstName}}": "测试收件人",
        "{{.LastName}}": "演示",
        "{{.Department}}": "安全演练测试",
        "{{.Email}}": to,
        "{{.Date}}": datetime.now().strftime("%Y-%m-%d"),
        "{{.ResetURL}}": landing_url,
    }

    if tpl:
        subject = tpl.subject or ""
        html = tpl.html_body or ""
    else:
        subject = "【PhishLab】演练邮件预览"
        html = (
            "<div style='font-family:sans-serif;line-height:1.8'>"
            "<p>这是一封演练邮件预览（未选择模板）。</p>"
            f"<p><a href='{landing_url or '#'}'>点击此处查看落地页 →</a></p></div>"
        )
    for k, v in var_map.items():
        subject = subject.replace(k, v)
        html = html.replace(k, v)

    # 二维码变量：{{.QRCode}} → 落地页链接二维码（附件 + 正文内嵌）
    attachments: list[dict] = []
    if "{{.QRCode}}" in html:
        from app.core.qr import render_qr_png

        qr_png = render_qr_png(landing_url)
        attachments.append({
            "filename": "操作指引二维码.png",
            "content": qr_png,
            "content_id": "qr_code",
        })
        html = html.replace(
            "{{.QRCode}}",
            '<div style="margin:16px 0;text-align:center">'
            '<img src="cid:qr_code" width="160" height="160" alt="二维码" '
            'style="border:1px solid #e8e8e8;border-radius:8px" />'
            '<div style="font-size:12px;color:#888;margin-top:6px">'
            '请使用手机扫描上方二维码（或下载附件）完成操作</div></div>',
        )

    # 落地页未被模板引用时，追加一个明显的落地页链接（模拟真实演练邮件的钩子）
    if lp and "{{.ResetURL}}" not in html and landing_url not in html:
        html += (
            f"<div style='font-family:sans-serif;margin-top:16px'>"
            f"<a href='{landing_url}'>立即处理 →</a></div>"
        )
    # 测试邮件水印，避免与真实演练邮件混淆
    html += (
        "<div style='margin-top:24px;padding-top:8px;border-top:1px dashed #ccc;"
        "font-size:11px;color:#999'>"
        "【测试邮件】来自演练向导预览 · 仅用于验证通道与内容呈现效果</div>"
    )

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
    sender_name = payload.get("sender_name") or ch.name
    result = _smtp_send(ch.name, cfg, to, subject=subject, html_body=html,
                        sender_name=sender_name, attachments=attachments)

    ch.last_test_result = result
    ch.last_test_at = datetime.now()
    if ch.status != "disabled":
        ch.status = "normal" if result["ok"] else ch.status
    db.commit()
    record_audit(
        db, account=account, module="channel", action="send_test_email_with_content",
        target_type="send_channel", target_id=ch.id,
        detail={"to": to, "template_id": payload.get("template_id"),
                "landing_page_id": payload.get("landing_page_id"), "ok": result["ok"]},
    )
    return result


def test_channel(db, account, channel_id: int, to: str | None = None) -> dict:
    """连通性复测，结果回写 last_test_result/last_test_at。"""
    ch = db.get(SendChannel, channel_id)
    if ch is None:
        raise BizError(ErrorCode.NOT_FOUND)
    if ch.type == "sms":
        result = {"ok": True, "score": 80, "latency_ms": None, "message": "SMS 通道已保存，发送能力待真机验证"}
    elif ch.type == "smtp":
        port = ch.smtp_port or (465 if ch.smtp_encrypt == "ssl" else 587)
        result = _tcp_probe(ch.smtp_host, port)
    else:  # ews
        host = urlparse(ch.ews_url).hostname if ch.ews_url else None
        result = _tcp_probe(host, 443)
    ch.last_test_result = result
    ch.last_test_at = datetime.now()
    if ch.status != "disabled":  # 管理员手动停用不因测试翻转
        ch.status = "normal" if result["ok"] else "abnormal"
    db.commit()
    return result


# ---------- 域名 DNS ----------

def list_domains(db, account) -> list[dict]:
    """演练域名列表（无分页），含 DNS 状态与送达评分。"""
    rows = db.scalars(select(PhishDomain).order_by(PhishDomain.id.desc())).all()
    return [
        {
            "id": d.id,
            "domain": d.domain,
            "spf": _STATUS_TEXT.get(d.spf_status, "WARN"),
            "dkim": _STATUS_TEXT.get(d.dkim_status, "WARN"),
            "dmarc": _STATUS_TEXT.get(d.dmarc_status, "WARN"),
            "score": d.deliver_score,
            "last_check": d.last_check_at.strftime("%Y-%m-%d %H:%M") if d.last_check_at else "",
        }
        for d in rows
    ]


def add_domain(db, account, payload: dict) -> int:
    """录入演练域名：生成 DKIM RSA2048 密钥对（私钥加密入库），输出 DNS 指引。"""
    domain = (payload.get("domain") or "").strip().lower()
    if not domain:
        raise BizError(ErrorCode.PARAM_INVALID, "域名不能为空")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    tips = (
        f'SPF：TXT @ → "v=spf1 mx ~all"\n'
        f'DKIM：TXT phish._domainkey.{domain} → "v=DKIM1; k=rsa; p=<平台生成的DKIM公钥>"\n'
        f'DMARC：TXT _dmarc.{domain} → "v=DMARC1; p=none; rua=mailto:dmarc@{domain}"'
    )
    d = PhishDomain(
        domain=domain,
        purpose=payload.get("purpose"),
        dkim_public_key=pub_pem,
        dkim_private_key_enc=encrypt_secret(priv_pem),
        repair_tips=tips,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    record_audit(
        db, account=account, module="channel", action="add_domain",
        target_type="phish_domain", target_id=d.id, detail={"domain": domain},
    )
    return d.id


def _record_exists(name: str, rdtype: str) -> bool:
    """记录存在性：NXDOMAIN/NoAnswer 视为不存在，解析器故障向上抛。"""
    try:
        dns.resolver.resolve(name, rdtype, lifetime=5)
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False


def check_dns(db, account, domain_id: int) -> dict:
    """DNS 巡检 SPF/DKIM/DMARC/MX，各 25 分计入送达评分；解析失败回退库内缓存。"""
    d = db.get(PhishDomain, domain_id)
    if d is None:
        raise BizError(ErrorCode.NOT_FOUND)
    try:
        spf = "ok" if _record_exists(d.domain, "TXT") else "fail"
        dkim = "ok" if _record_exists(f"{d.dkim_selector}._domainkey.{d.domain}", "TXT") else "fail"
        dmarc = "ok" if _record_exists(f"_dmarc.{d.domain}", "TXT") else "fail"
        mx = "ok" if _record_exists(d.domain, "MX") else "fail"
        score = sum(25 for s in (spf, dkim, dmarc, mx) if s == "ok")
        d.spf_status, d.dkim_status, d.dmarc_status, d.mx_status = spf, dkim, dmarc, mx
        d.deliver_score = score
        d.last_check_at = datetime.now()
        db.commit()
        tips = d.repair_tips or ""
    except (dns.exception.DNSException, OSError):
        # 离线/解析器故障：保留库内缓存值，仅刷新检测时间
        d.last_check_at = datetime.now()
        db.commit()
        tips = "DNS 解析失败（离线环境），已返回缓存结果"
    return {
        "id": d.id,
        "domain": d.domain,
        "spf": _STATUS_TEXT.get(d.spf_status, "WARN"),
        "dkim": _STATUS_TEXT.get(d.dkim_status, "WARN"),
        "dmarc": _STATUS_TEXT.get(d.dmarc_status, "WARN"),
        "mx": _STATUS_TEXT.get(d.mx_status, "WARN"),
        "score": d.deliver_score,
        "tips": tips,
    }


# ---------- 伪装发件人 ----------


def delete_domain(db, account, domain_id: int) -> None:
    """删除域名（软约束：关联演练保留 ID 引用）。"""
    d = db.get(PhishDomain, domain_id)
    if d is None:
        raise ValueError("域名不存在")
    db.delete(d)
    db.commit()
    record_audit(
        db, account=account, module="channel", action="delete_domain",
        target_type="phish_domain", target_id=domain_id,
    )


def list_sender_profiles(db, account) -> list[dict]:
    """伪装发件人列表；channel 显示关联通道名（未指定时取默认 SMTP 通道），与 test_sender_profile 口径一致。"""
    channels = {c.id: c.name for c in db.scalars(select(SendChannel)).all()}
    default_ch = db.scalar(
        select(SendChannel)
        .where(SendChannel.type == "smtp", SendChannel.status != "disabled")
        .order_by(SendChannel.is_default.desc(), SendChannel.id.desc())
        .limit(1)
    )
    default_name = default_ch.name if default_ch else ""
    rows = db.scalars(select(SenderProfile).order_by(SenderProfile.id.desc())).all()
    return [
        {
            "id": p.id,
            "channel_id": p.channel_id,
            "display_name": p.display_name or p.name,
            "address": p.from_addr or "",
            "reply_to": p.reply_to or "",
            "scene_tags": p.scene_tags or [],
            "channel": channels.get(p.channel_id) if p.channel_id else default_name,
        }
        for p in rows
    ]


def create_sender_profile(db, account, payload: dict) -> int:
    p = SenderProfile(
        name=payload["name"],
        channel_type=payload.get("channel_type") or "mail",
        channel_id=payload.get("channel_id"),
        display_name=payload.get("display_name"),
        from_addr=payload.get("from_addr"),
        reply_to=payload.get("reply_to"),
        sms_number=payload.get("sms_number"),
        sms_sign=payload.get("sms_sign"),
        scene_tags=payload.get("scene_tags") or [],
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    record_audit(
        db, account=account, module="channel", action="create_sender_profile",
        target_type="sender_profile", target_id=p.id,
    )
    return p.id


def update_sender_profile(db, account, pid: int, payload: dict) -> int:
    """更新伪装发件人（编辑保存）。"""
    p = db.get(SenderProfile, pid)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "伪装发件人不存在")
    p.name = payload["name"]
    p.channel_type = payload.get("channel_type") or "mail"
    p.channel_id = payload.get("channel_id")
    p.display_name = payload.get("display_name")
    p.from_addr = payload.get("from_addr")
    p.reply_to = payload.get("reply_to")
    p.sms_number = payload.get("sms_number")
    p.sms_sign = payload.get("sms_sign")
    p.scene_tags = payload.get("scene_tags") or []
    db.commit()
    record_audit(
        db, account=account, module="channel", action="update_sender_profile",
        target_type="sender_profile", target_id=p.id,
    )
    return p.id


def delete_sender_profile(db, account, pid: int) -> None:
    """删除伪装发件人；已被演练引用时拒绝删除。"""
    p = db.get(SenderProfile, pid)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "伪装发件人不存在")
    used = db.scalar(
        select(Campaign.id).where(Campaign.sender_profile_id == pid).limit(1)
    )
    if used is not None:
        raise BizError(ErrorCode.BIZ_CONFLICT, "该伪装发件人已被演练引用，请先更换演练中的伪装发件人")
    db.delete(p)
    db.commit()
    record_audit(
        db, account=account, module="channel", action="delete_sender_profile",
        target_type="sender_profile", target_id=pid,
    )


# 公共邮箱域：强制 From 地址 == 发送账号（QQ/163 等不允许 From 与账号不一致）
_PUBLIC_MAIL_DOMAINS = {
    "qq.com", "foxmail.com", "163.com", "126.com", "139.com",
    "sina.com", "gmail.com", "outlook.com", "hotmail.com",
}


def test_sender_profile(db, account, pid: int, to: str) -> dict:
    """用伪装发件人（显示名 + From 地址）通过关联 SMTP 通道真实发送测试邮件。

    未指定关联通道时回退默认 SMTP 通道；发件信封使用通道发送账号（保证送达），
    收件端展示的 From 头为伪装发件人。公共邮箱通道下 From 地址自动回退为发送账号
    （仅保留显示名伪装，否则 QQ/163 按反垃圾策略拒收）。
    """
    from app.core.security import decrypt_secret

    p = db.get(SenderProfile, pid)
    if p is None:
        raise BizError(ErrorCode.NOT_FOUND, "伪装发件人不存在")
    if not to:
        raise BizError(ErrorCode.PARAM_INVALID, "请填写测试收件邮箱")

    if p.channel_id:
        ch = db.get(SendChannel, p.channel_id)
        if ch is None or ch.type != "smtp" or ch.status == "disabled":
            raise BizError(ErrorCode.PARAM_INVALID, "关联通道不存在或不可用，请编辑伪装发件人重新选择")
    else:
        ch = db.scalar(
            select(SendChannel)
            .where(SendChannel.type == "smtp", SendChannel.status != "disabled")
            .order_by(SendChannel.is_default.desc(), SendChannel.id.desc())
            .limit(1)
        )
    if ch is None:
        raise BizError(ErrorCode.NOT_FOUND, "未找到可用 SMTP 发送通道，请先配置 SMTP 通道")

    acct = (ch.smtp_username or "").strip()
    from_addr = p.from_addr or None
    note = ""
    if from_addr:
        acct_domain = acct.split("@")[-1].lower() if "@" in acct else ""
        if acct_domain in _PUBLIC_MAIL_DOMAINS and from_addr != acct:
            # 公共邮箱强制 From == 发送账号（含同域不同账号也会拒收），保留显示名伪装
            from_addr = None
            note = "该通道为公共邮箱（QQ/163 等），From 地址已自动回退为发送账号；伪装显示名仍生效"

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
    result = _smtp_send(
        ch.name, cfg, to,
        sender_name=p.display_name or p.name,
        from_addr=from_addr,
    )
    if note:
        result["note"] = note
    record_audit(
        db, account=account, module="channel", action="test_sender_profile",
        target_type="sender_profile", target_id=pid,
        detail={"to": to, "ok": result["ok"], "display_name": p.display_name,
                "from_addr": p.from_addr, "actual_from": acct if from_addr is None else from_addr},
    )
    return result
