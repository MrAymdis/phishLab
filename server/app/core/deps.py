"""鉴权与数据权限依赖。"""
from fastapi import Depends, Header
from sqlalchemy import false, or_, select
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
    """接口/按钮级权限校验工厂（RBAC）。

    - super_admin 角色直接放行
    - 其余角色经 sys_role_permission → sys_permission.perm_code 校验
    - 权限未定义/未授权时默认拒绝（安全兜底：写操作校验失败即拦截，红线相关）
    """

    def _checker(account=Depends(get_current_account), db: Session = Depends(get_db)):
        from app.modules.rbac.models import SysAccountRole, SysPermission, SysRole, SysRolePermission

        role_ids = db.scalars(
            select(SysAccountRole.role_id).where(SysAccountRole.account_id == account.id)
        ).all()
        if not role_ids:
            raise BizError(ErrorCode.PERM_DENIED, "账号未分配角色，无操作权限")
        if db.scalar(
            select(SysRole.id).where(SysRole.id.in_(role_ids), SysRole.code == "super_admin")
        ):
            return account
        granted = db.scalar(
            select(SysPermission.id)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .where(
                SysRolePermission.role_id.in_(role_ids),
                SysPermission.perm_code == perm_code,
            )
            .limit(1)
        )
        if granted is None:
            raise BizError(ErrorCode.PERM_DENIED, f"无操作权限（{perm_code}）")
        return account

    return _checker


def apply_data_scope(db, stmt, account, *, dept_col=None, self_owner_col=None, self_id=None,
                     allow_null_owner: bool = False):
    """SQL 级数据权限过滤（全部/本部门及子级/本部门/仅本人/自定义部门）。

    - 无角色 / super_admin / data_scope==1 → 原样返回
    - scope 2: 本部门及子级（EmpDept.path LIKE '/{dept}/%'）
    - scope 3: 本部门
    - scope 4: 仅本人（self_owner_col == account.id 或 self_id）
    - scope 5: sys_role_dept 自定义部门
    所有列表/报表查询必须经过本函数，禁止裸查询。
    dept_col 传 None 时不做部门过滤（如 Campaign 无部门列，仅按创建人过滤）。
    allow_null_owner=True 时「仅本人」也放行归属为空的行（平台内置素材 created_by IS NULL）。
    仅本人但无任何归属字段可过滤时默认拒绝（共享基础设施的安全兜底）。
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
            cond = self_owner_col == account.id
            if allow_null_owner:
                cond = or_(cond, self_owner_col.is_(None))
            conds.append(cond)
        elif self_id is not None:
            conds.append(self_id == account.emp_user_id)
        else:
            # 无归属字段的共享资源（通道/域名等）：仅本人角色默认不可见
            conds.append(false())
    if conds:
        stmt = stmt.where(or_(*conds))
    return stmt
