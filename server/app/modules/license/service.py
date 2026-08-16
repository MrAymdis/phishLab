"""License 服务占位：激活/校验/配额前置检查。

所有资源创建入口（演练/员工/发送）前必须调用 check_quota。
"""
from app.core.errors import BizError, ErrorCode

# 功能模块按版本开关：flagship 才有高级 AI / 开放平台
EDITION_FEATURES = {
    "trial": {"ai": True, "openapi": False, "payload": False},
    "standard": {"ai": True, "openapi": False, "payload": False},
    "flagship": {"ai": True, "openapi": True, "payload": True},
}


def get_status(db) -> dict:
    """授权状态概览：版本/到期/配额用量进度。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def activate_online(db, license_key: str) -> dict:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def activate_offline(db, lic_bytes: bytes) -> dict:
    """离线 .lic：RSA 签名校验。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def check_quota(db, resource: str, amount: int = 1) -> None:
    """resource: user/mail/sms/campaign；超限抛 LICENSE_EXCEEDED。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def feature_enabled(db, feature: str) -> bool:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
