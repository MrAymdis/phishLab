"""License 服务：激活/校验/配额前置检查。

所有资源创建入口（演练/员工/发送）前必须调用 check_quota。
离线 .lic：RSA-SHA256 签名验签 + license_no 防重放（红线：伪造/重放即拒绝）。
"""
import base64
import json
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError, ErrorCode

from .models import LicenseInfo, LicenseUsage

# 功能模块按版本开关：flagship 才有高级 AI / 开放平台
EDITION_FEATURES = {
    "trial": {"ai": True, "openapi": False, "payload": False},
    "standard": {"ai": True, "openapi": False, "payload": False},
    "flagship": {"ai": True, "openapi": True, "payload": True},
}

_PREFIX_EDITION = {"PL-TRIAL-": "trial", "PL-STD-": "standard", "PL-FLAG-": "flagship"}
_QUOTA_BY_EDITION = {
    "trial": {"user": 5000, "mail": 300000, "sms": 10000, "campaign": 200},
    "standard": {"user": 20000, "mail": 1000000, "sms": 50000, "campaign": 1000},
    "flagship": {"user": 100000, "mail": 10000000, "sms": 500000, "campaign": 10000},
}


def _get_license(db: Session) -> LicenseInfo | None:
    return db.scalar(select(LicenseInfo).order_by(LicenseInfo.id.desc()))


def _parse_key(license_key: str) -> dict:
    for prefix, edition in _PREFIX_EDITION.items():
        if license_key.startswith(prefix):
            code = license_key[len(prefix):]
            if len(code) < 4:
                raise BizError(ErrorCode.PARAM_INVALID, "激活码格式不正确")
            # 演示实现：code 第 1 位决定有效期月数（1/6/12），其余位为签名占位
            months = {"1": 1, "6": 6, "0": 12}.get(code[0], 1)
            return {"edition": edition, "months": months}
    raise BizError(ErrorCode.PARAM_INVALID, "激活码格式不正确（需以 PL-TRIAL-/PL-STD-/PL-FLAG- 开头）")


def get_status(db: Session) -> dict:
    """授权状态概览：版本/到期/配额用量进度。无 license 行时返回 trial 默认。"""
    lic = _get_license(db)
    if lic is None:
        return {
            "edition": "trial",
            "customer_name": "未激活客户",
            "status": "active",
            "activated_at": None,
            "expire_at": None,
            "remaining_days": 30,
            "features": EDITION_FEATURES["trial"],
            "quotas": {k: {"used": 0, "total": v} for k, v in _QUOTA_BY_EDITION["trial"].items()},
        }
    edition = lic.edition or "trial"
    quotas = dict(_QUOTA_BY_EDITION.get(edition, _QUOTA_BY_EDITION["trial"]))
    used = _usage(db)
    remaining = (lic.expire_at.date() - datetime.now().date()).days if lic.expire_at else 0
    return {
        "edition": edition,
        "customer_name": lic.customer_name,
        "status": lic.status,
        "activated_at": lic.activated_at,
        "expire_at": lic.expire_at,
        "remaining_days": max(remaining, 0),
        "features": EDITION_FEATURES.get(edition, EDITION_FEATURES["trial"]),
        "quotas": {
            k: {"used": used.get(k, 0), "total": v} for k, v in quotas.items()
        },
    }


def _usage(db: Session) -> dict:
    """配额用量：员工数 / license_usage 月度累计 / 演练数。"""
    from app.modules.campaign.models import Campaign
    from app.modules.org.models import EmpUser

    user_cnt = db.scalar(select(func.count()).select_from(EmpUser).where(EmpUser.status == 1)) or 0
    campaign_cnt = db.scalar(select(func.count()).select_from(Campaign)) or 0
    mails = db.scalar(select(func.coalesce(func.sum(LicenseUsage.mails_sent), 0))) or 0
    sms = db.scalar(select(func.coalesce(func.sum(LicenseUsage.sms_sent), 0))) or 0
    return {"user": user_cnt, "mail": int(mails), "sms": int(sms), "campaign": campaign_cnt}


def activate_online(db: Session, license_key: str) -> dict:
    parsed = _parse_key(license_key)
    _apply_license(db, license_key=license_key, edition=parsed["edition"],
                   months=parsed["months"], customer=None, mode="online")
    return get_status(db)


def _canonical_json(payload: dict) -> str:
    """签名规范形式：按键排序 + 紧凑分隔，保证签发端/验签端一致。"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_public_key():
    pem = (settings.license_public_key or "").strip()
    if not pem:
        raise BizError(ErrorCode.PERM_DENIED,
                       "离线激活未配置 RSA 公钥（LICENSE_PUBLIC_KEY），拒绝激活")
    try:
        return serialization.load_pem_public_key(pem.encode("utf-8"))
    except Exception:
        raise BizError(ErrorCode.PERM_DENIED, "LICENSE_PUBLIC_KEY 不是合法 PEM 公钥")


def _verify_offline(data: dict) -> dict:
    """.lic 验签 + 字段校验，通过返回归一化 payload（fail-closed）。"""
    payload = {k: data.get(k) for k in ("license_no", "customer", "edition", "months", "issued_at")}
    if not payload["license_no"] or not payload["customer"]:
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 字段缺失（license_no/customer）")
    if payload["edition"] not in _PREFIX_EDITION.values():
        raise BizError(ErrorCode.PARAM_INVALID, ".lic edition 非法（trial/standard/flagship）")
    try:
        payload["months"] = int(payload["months"])
        if not 1 <= payload["months"] <= 36:
            raise ValueError
    except (TypeError, ValueError):
        raise BizError(ErrorCode.PARAM_INVALID, ".lic months 需在 1-36 之间")
    if not payload["issued_at"]:
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 缺少 issued_at")
    try:
        signature = base64.b64decode(data.get("signature") or "", validate=True)
    except Exception:
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 签名编码不正确")
    pub = _load_public_key()
    try:
        pub.verify(signature, _canonical_json(payload).encode("utf-8"),
                   padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, ValueError):
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 签名校验失败，文件可能被篡改")
    return payload


def _apply_license(db: Session, *, license_key: str, edition: str, months: int,
                   customer: str, mode: str, signature: str | None = None) -> None:
    """激活写库（在线/离线共用）：配额按版本映射，到期 = 激活日 + 月数*30 天。"""
    expire_at = datetime.now() + timedelta(days=30 * months)
    lic = _get_license(db)
    if lic is None:
        lic = LicenseInfo(license_key=license_key)
        db.add(lic)
    lic.license_key = license_key
    lic.edition = edition
    lic.customer_name = customer or lic.customer_name or "演示客户"
    lic.user_quota = _QUOTA_BY_EDITION[edition]["user"]
    lic.mail_quota = _QUOTA_BY_EDITION[edition]["mail"]
    lic.sms_quota = _QUOTA_BY_EDITION[edition]["sms"]
    lic.campaign_quota = _QUOTA_BY_EDITION[edition]["campaign"]
    lic.activate_mode = mode
    lic.signature = signature
    lic.activated_at = datetime.now()
    lic.expire_at = expire_at
    lic.status = "active"
    db.commit()


def activate_offline(db: Session, lic_bytes: bytes) -> dict:
    """离线 .lic：RSA-SHA256 验签 → 防重放（license_no 唯一）→ 激活。"""
    try:
        data = json.loads(lic_bytes.decode("utf-8", errors="ignore").strip())
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, json.JSONDecodeError):
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 不是合法 JSON")
    payload = _verify_offline(data)
    # 防重放：同一 license_no 已激活（在线/离线共用 key 维度）则拒绝
    exist = db.scalar(select(LicenseInfo).where(LicenseInfo.license_key == payload["license_no"]))
    if exist is not None:
        raise BizError(ErrorCode.BIZ_CONFLICT,
                       f"授权文件 {payload['license_no']} 已激活（防重放），如需升级请使用新授权文件")
    _apply_license(db, license_key=payload["license_no"], edition=payload["edition"],
                   months=payload["months"], customer=payload["customer"],
                   mode="offline", signature=data["signature"])
    return get_status(db)


def check_quota(db: Session, resource: str, amount: int = 1) -> None:
    """resource: user/mail/sms/campaign；超限抛 LICENSE_EXCEEDED。无 license 行放行。"""
    lic = _get_license(db)
    if lic is None or resource not in _QUOTA_BY_EDITION.get(lic.edition or "trial", {}):
        return
    quota = _QUOTA_BY_EDITION[lic.edition][resource]
    used = _usage(db).get(resource, 0)
    if used + amount > quota:
        raise BizError(ErrorCode.LICENSE_EXCEEDED, f"{resource} 配额已用尽（{used}/{quota}）")


def feature_enabled(db: Session, feature: str) -> bool:
    lic = _get_license(db)
    if lic is None:  # 未激活：开发环境全量放行，避免空导航
        return True
    return EDITION_FEATURES.get(lic.edition or "trial", {}).get(feature, False)
