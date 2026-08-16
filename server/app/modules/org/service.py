"""组织与员工服务占位。"""
from app.core.errors import BizError, ErrorCode


def dept_tree(db, account) -> list[dict]:
    """部门树（含人数）。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_dept(db, account, payload: dict) -> int:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def sync_org(db, account, source: str) -> dict:
    """触发 LDAP/企微/钉钉/飞书 同步。TODO(二期)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_users(db, account, *, dept_id=None, tag=None, risk_level=None, kw=None, page=1, page_size=20):
    """员工档案列表：手机掩码，数据权限过滤。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_user(db, account, payload: dict) -> int:
    """手机 encrypt_secret 入库；初始化风险画像。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def get_user(db, account, user_id: int) -> dict:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def get_risk_profile(db, account, user_id: int) -> dict:
    """五维雷达 + 历史轨迹。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_groups(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def list_tags(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
