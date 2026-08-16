"""发送配置服务：通道连通性探测、演练域名 DNS 巡检、伪装发件人。"""
import socket
import time
from datetime import datetime
from urllib.parse import urlparse

import dns.exception
import dns.resolver
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.core.audit import record_audit
from app.core.errors import BizError, ErrorCode
from app.core.security import encrypt_secret

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
            }
        )
    return result


def create_channel(db, account, payload: dict) -> int:
    """新建通道：敏感字段 AES-GCM 加密入库；保存前做 TCP 连通探测。"""
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
            smtp_encrypt=cfg.get("smtp_encryption"),
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

    # 保存前连通测试；SMS 通道仅登记，发送能力待真机验证
    if ch_type == "sms":
        result = {"ok": True, "score": 80, "latency_ms": None, "message": "SMS 通道已保存，发送能力待真机验证"}
        status = "normal"
    else:
        result = _tcp_probe(*_resolve_probe_target(ch_type, cfg))
        status = "normal" if result["ok"] else "abnormal"

    ch = SendChannel(**kw, status=status, last_test_result=result, last_test_at=datetime.now())
    db.add(ch)
    db.commit()
    db.refresh(ch)
    record_audit(
        db, account=account, module="channel", action="create_channel",
        target_type="send_channel", target_id=ch.id, detail={"type": ch_type},
    )
    return ch.id


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

def list_sender_profiles(db, account) -> list[dict]:
    """伪装发件人列表；channel 取当前默认发送通道名。"""
    default_channel = db.scalar(select(SendChannel.name).where(SendChannel.is_default == 1))
    rows = db.scalars(select(SenderProfile).order_by(SenderProfile.id.desc())).all()
    return [
        {
            "id": p.id,
            "display_name": p.display_name or p.name,
            "address": p.from_addr or "",
            "reply_to": p.reply_to or "",
            "scene_tags": p.scene_tags or [],
            "channel": default_channel or "",
        }
        for p in rows
    ]


def create_sender_profile(db, account, payload: dict) -> int:
    p = SenderProfile(
        name=payload["name"],
        channel_type=payload.get("channel_type") or "mail",
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
