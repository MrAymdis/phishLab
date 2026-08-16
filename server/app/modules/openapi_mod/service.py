"""开放平台服务占位（三期模块）。OAuth2 client_credentials + 限流网关。"""
from app.core.errors import BizError, ErrorCode


def list_apps(db, account):
    """AppSecret 只回显掩码。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_app(db, account, payload: dict) -> dict:
    """生成 AppID/AppSecret（encrypt_secret 入库）、scope、IP 白名单、限流。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def issue_token(db, app_id: str, app_secret: str) -> dict:
    """client_credentials → 短期 JWT；校验状态/IP 白名单。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
