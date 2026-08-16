"""鉴权与数据权限依赖。"""
from fastapi import Depends, Header
from sqlalchemy import or_, select
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


def apply_data_scope(db, stmt, account, *, dept_col=None, self_owner_col=None, self_id=None):
    """SQL 级数据权限过滤（全部/本部门及子级/本部门/仅本人/自定义部门）。

    - 无角色 / super_admin / data_scope==1 → 原样返回
    - scope 2: 本部门及子级（EmpDept.path LIKE '/{dept}/%'）
    - scope 3: 本部门
    - scope 4: 仅本人（self_owner_col == account.id 或 self_id）
    - scope 5: sys_role_dept 自定义部门
    所有列表/报表查询必须经过本函数，禁止裸查询。
    dept_col 传 None 时不做部门过滤（如 Campaign 无部门列，仅按创建人过滤）。
    """
    from app.modules.org.models import EmpDept, EmpUser  # 延迟导入避免循环
    from app.modules.rbac.models import SysAccountRole, SysRole, SysRoleDept

    roles = db.scalars(
        select(SysRole)
        .join(SysAccountRole, SysAccountRole.role_id == SysRole.id)
        .where(SysAccountRole.account_id == account.id)
    ).all()
    if not roles:
        return stmt  # 无角色（测试/未配置）放行
    if any(r.code == "super_admin" or r.data_scope == 1 for r in roles):
        return stmt

    own_dept_id = None
    if account.emp_user_id:
        eu = db.get(EmpUser, account.emp_user_id)
        own_dept_id = eu.dept_id if eu else None

    dept_ids: set[int] = set()
    self_only = False
    for r in roles:
        if r.data_scope == 4:
            self_only = True
        elif r.data_scope in (2, 3) and own_dept_id:
            dept_ids.add(own_dept_id)
            if r.data_scope == 2:  # 本部门及子级
                own = db.get(EmpDept, own_dept_id)
                if own:
                    dept_ids.update(
                        d.id for d in db.scalars(
                            select(EmpDept).where(EmpDept.path.like(f"{own.path.rstrip('/')}/%"))
                        ).all()
                    )
        elif r.data_scope == 5:
            dept_ids.update(
                did for did in db.scalars(
                    select(SysRoleDept.dept_id).where(SysRoleDept.role_id == r.id)
                ).all()
            )

    conds = []
    if dept_ids and dept_col is not None:
        conds.append(dept_col.in_(dept_ids))
    if self_only:
        # self_owner_col: 列 == account.id（如 Campaign.creator_id）
        # self_id: 列 == account.emp_user_id（如 EmpUser.id）
        if self_owner_col is not None:
            conds.append(self_owner_col == account.id)
        elif self_id is not None:
            conds.append(self_id == account.emp_user_id)
    if conds:
        stmt = stmt.where(or_(*conds))
    return stmt
