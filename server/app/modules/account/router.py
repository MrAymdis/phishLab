from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service, schemas

auth = APIRouter(prefix="/api/v1/auth", tags=["认证"])
accounts = APIRouter(prefix="/api/v1/accounts", tags=["平台账号"], dependencies=[Depends(require_perm("system:account"))])
routers = [auth, accounts]


@auth.post("/login", summary="登录")
def login(req: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    return resp.ok(service.login(db, req, ip=request.client.host if request.client else None))


@auth.get("/init-status", summary="系统是否已初始化（无鉴权，登录页引导用）")
def init_status(db: Session = Depends(get_db)):
    from sqlalchemy import func, select

    from .models import SysAccount

    initialized = db.scalar(select(func.count()).select_from(SysAccount)) > 0
    return resp.ok({"initialized": initialized})


@auth.post("/init", summary="首启初始化超级管理员（仅系统无任何账号时可用）")
def init_system(payload: schemas.InitRequest, db: Session = Depends(get_db)):
    acc = service.bootstrap_super_admin(db, payload.username, payload.password, payload.real_name)
    return resp.ok({"id": acc.id, "username": acc.username})


@auth.get("/me", summary="当前账号信息")
def me(account=Depends(get_current_account)):
    return resp.ok(schemas.AccountOut.model_validate(account))


@auth.get("/menus", summary="当前账号菜单（RBAC ∩ License）")
def menus(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_menus(db, account))


@auth.put("/profile", summary="个人中心：修改本人资料")
def update_profile(payload: schemas.ProfileUpdate, account=Depends(get_current_account),
                   db: Session = Depends(get_db)):
    service.update_profile(db, account, payload)
    return resp.ok(None)


@auth.put("/password", summary="个人中心：修改本人密码（验旧密码）")
def change_password(payload: schemas.PasswordChange, account=Depends(get_current_account),
                    db: Session = Depends(get_db)):
    service.change_password(db, account, payload)
    return resp.ok(None)


@accounts.get("", summary="平台账号分页列表（含角色）")
def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    kw: str = Query("", description="用户名/姓名模糊"),
    db: Session = Depends(get_db),
):
    return resp.ok(service.list_accounts(db, page=page, page_size=page_size, kw=kw))


@accounts.post("", summary="新建平台账号")
def create_account(payload: schemas.AccountCreate, account=Depends(get_current_account),
                   db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_account(db, account, payload)})


@accounts.put("/{aid}", summary="更新账号资料/状态/角色")
def update_account(aid: int, payload: schemas.AccountUpdate,
                   account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.update_account(db, account, aid, payload)
    return resp.ok(None)


@accounts.put("/{aid}/password", summary="管理员重置密码")
def reset_password(aid: int, payload: schemas.PasswordReset,
                   account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.reset_password(db, account, aid, payload.new_password)
    return resp.ok(None)
