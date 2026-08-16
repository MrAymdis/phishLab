"""鉴权与数据权限依赖。"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from .errors import BizError, ErrorCode
from .security import decode_token


def get_current_account(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """解析 Bearer Token 并加载平台账号。"""
    from app.modules.account.models import SysAccount  # 延迟导入避免循环

    if not authorization or not authorization.lower().startswith("bearer "):
        raise BizError(ErrorCode.UNAUTHORIZED)
    payload = decode_token(authorization[7:].strip())
    account = db.get(SysAccount, int(payload["sub"]))
    if account is None or account.status != 1:
        raise BizError(ErrorCode.ACCOUNT_DISABLED)
    return account


def require_perm(perm_code: str):
    """按钮/接口级权限校验工厂。

    TODO(一期实现)：加载账号角色 → sys_role_permission → 校验 perm_code；
    超管 super_admin 直接放行。
    """

    def _checker(account=Depends(get_current_account)):
        # 脚手架阶段：仅校验已登录
        return account

    return _checker


def apply_data_scope(query, account):
    """SQL 级数据权限过滤（全部/本部门及子级/本部门/仅本人/自定义部门）。

    TODO(一期实现)：按 account 角色的 data_scope 拼接 dept_id 过滤条件；
    所有列表/报表查询必须经过本函数，禁止裸查询。
    """
    return query
