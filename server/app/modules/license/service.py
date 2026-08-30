"""License 服务：激活/校验/配额前置检查（fail-closed 强制）。

授权模型：
- 无授权行 → 演示模式（demo）：试用版功能 + 演示小配额兜底，不再全量放行；
- 授权有效 → 按版本（trial/standard/flagship）开放功能与配额；
- 授权过期/吊销/机器码不匹配 → 禁止新建资源、gated 功能全关（禁止新建/投递，查看不受限）。

激活只有一条路：离线 .lic（RSA-SHA256 签名 + license_no 防重放 + 机器码部署绑定）。
在线 PL- 前缀激活码已移除（可被随意伪造，见历史演示实现 _parse_key）。
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

from .fingerprint import get_machine_code
from .models import LicenseInfo, LicenseUsage

# 功能模块按版本开关：flagship 才有高级 AI / 开放平台 / 宏 EXE 载荷（红线 6）
EDITION_FEATURES = {
    "trial": {"ai": True, "openapi": False, "payload": False},
    "standard": {"ai": True, "openapi": False, "payload": False},
    "flagship": {"ai": True, "openapi": True, "payload": True},
}

_EDITIONS = set(EDITION_FEATURES)
_QUOTA_BY_EDITION = {
    "trial": {"user": 5000, "mail": 300000, "sms": 10000, "campaign": 200},
    "standard": {"user": 20000, "mail": 1000000, "sms": 50000, "campaign": 1000},
    "flagship": {"user": 100000, "mail": 10000000, "sms": 500000, "campaign": 10000},
}
# 演示模式配额（未激活兜底）：足够评估，但与正式授权拉开量级
_DEMO_QUOTA = {"user": 500, "mail": 5000, "sms": 500, "campaign": 20}

_STATE_CN = {"demo": "未激活（演示模式）", "expired": "授权已过期",
             "invalid": "授权与本机不匹配", "revoked": "授权已被吊销"}


def _get_license(db: Session) -> LicenseInfo | None:
    return db.scalar(select(LicenseInfo).order_by(LicenseInfo.id.desc()))


def _license_state(db: Session) -> str:
    """运行时授权状态：demo / active / expired / invalid / revoked（fail-closed）。"""
    lic = _get_license(db)
    if lic is None:
        return "demo"
    if lic.status == "revoked":
        return "revoked"
    if not lic.expire_at or lic.expire_at < datetime.now():
        return "expired"
    if not lic.machine_code or lic.machine_code != get_machine_code():
        return "invalid"
    if lic.status != "active":
        return "invalid"
    return "active"


def get_status(db: Session) -> dict:
    """授权状态概览：版本/到期/配额用量进度 + 部署绑定信息。"""
    lic = _get_license(db)
    state = _license_state(db)
    used = _usage(db)

    if lic is None:
        edition, features, quotas = "trial", EDITION_FEATURES["trial"], _DEMO_QUOTA
        return {
            "edition": edition,
            "customer_name": "未激活客户",
            "status": "demo",
            "demo_mode": True,
            "activated_at": None,
            "expire_at": None,
            "remaining_days": None,
            "features": features,
            "quotas": {k: {"used": used.get(k, 0), "total": v} for k, v in quotas.items()},
            "machine_code": get_machine_code(),
            "bound_machine_code": None,
        }

    edition = lic.edition or "trial"
    blocked = state not in ("active", "demo")
    remaining = (lic.expire_at.date() - datetime.now().date()).days if lic.expire_at else 0
    return {
        "edition": edition,
        "customer_name": lic.customer_name,
        "status": state if state != "active" else lic.status,
        "demo_mode": False,
        "activated_at": lic.activated_at,
        "expire_at": lic.expire_at,
        "remaining_days": max(remaining, 0),
        "features": {} if blocked else EDITION_FEATURES.get(edition, EDITION_FEATURES["trial"]),
        "quotas": {
            k: {"used": used.get(k, 0), "total": v}
            for k, v in _QUOTA_BY_EDITION.get(edition, _QUOTA_BY_EDITION["trial"]).items()
        },
        "machine_code": get_machine_code(),
        "bound_machine_code": lic.machine_code,
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
    """.lic 验签 + 字段校验 + 机器码绑定校验，通过返回归一化 payload（fail-closed）。"""
    payload = {k: data.get(k) for k in ("license_no", "customer", "edition", "months",
                                        "issued_at", "machine_code")}
    if not payload["license_no"] or not payload["customer"]:
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 字段缺失（license_no/customer）")
    if payload["edition"] not in _EDITIONS:
        raise BizError(ErrorCode.PARAM_INVALID, ".lic edition 非法（trial/standard/flagship）")
    try:
        payload["months"] = int(payload["months"])
        if not 1 <= payload["months"] <= 36:
            raise ValueError
    except (TypeError, ValueError):
        raise BizError(ErrorCode.PARAM_INVALID, ".lic months 需在 1-36 之间")
    if not payload["issued_at"]:
        raise BizError(ErrorCode.PARAM_INVALID, ".lic 缺少 issued_at")
    if not payload["machine_code"]:
        raise BizError(ErrorCode.PARAM_INVALID,
                       ".lic 缺少 machine_code（部署绑定字段），请向供应商申请重新签发")
    if payload["machine_code"] != get_machine_code():
        raise BizError(ErrorCode.PERM_DENIED,
                       f"授权文件与当前部署机器不匹配（绑定机器码 "
                       f"{payload['machine_code'][:12]}…，本机 {get_machine_code()[:12]}…），"
                       f"请向供应商申请重签发")
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
                   customer: str, mode: str, machine_code: str,
                   signature: str | None = None) -> None:
    """激活写库：配额按版本映射，到期 = 激活日 + 月数*30 天，绑定机器码。"""
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
    lic.machine_code = machine_code
    lic.activated_at = datetime.now()
    lic.expire_at = expire_at
    lic.status = "active"
    db.commit()


def activate_offline(db: Session, lic_bytes: bytes) -> dict:
    """离线 .lic：RSA-SHA256 验签 + 机器码绑定 → 防重放（license_no 唯一）→ 激活。"""
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
                   mode="offline", machine_code=payload["machine_code"],
                   signature=data["signature"])
    return get_status(db)


def check_quota(db: Session, resource: str, amount: int = 1) -> None:
    """resource: user/mail/sms/campaign；超限抛 LICENSE_EXCEEDED。

    演示模式走小配额兜底；过期/吊销/机器不匹配直接禁止新建（fail-closed）。
    """
    lic = _get_license(db)
    state = _license_state(db)
    if state == "demo":
        quotas = _DEMO_QUOTA
    elif state == "active":
        quotas = _QUOTA_BY_EDITION.get(lic.edition or "trial", _QUOTA_BY_EDITION["trial"])
    else:
        raise BizError(ErrorCode.LICENSE_INVALID,
                       f"{_STATE_CN[state]}，禁止新建资源/投递，请联系供应商续期或重签发授权")
    if resource not in quotas:
        return
    used = _usage(db).get(resource, 0)
    if used + amount > quotas[resource]:
        raise BizError(ErrorCode.LICENSE_EXCEEDED,
                       f"{resource} 配额已用尽（{used}/{quotas[resource]}）")


def feature_enabled(db: Session, feature: str) -> bool:
    """功能门控（fail-closed）：演示模式=试用版能力；失效=全关。"""
    lic = _get_license(db)
    state = _license_state(db)
    if state == "demo":
        return EDITION_FEATURES["trial"].get(feature, False)
    if state != "active":
        return False
    return EDITION_FEATURES.get(lic.edition or "trial", {}).get(feature, False)
