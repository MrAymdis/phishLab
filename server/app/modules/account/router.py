from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.db.session import get_db

from . import service, schemas

auth = APIRouter(prefix="/api/v1/auth", tags=["认证"])
routers = [auth]


@auth.post("/login", summary="登录")
def login(req: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    return resp.ok(service.login(db, req, ip=request.client.host if request.client else None))


@auth.get("/me", summary="当前账号信息")
def me(account=Depends(get_current_account)):
    return resp.ok(schemas.AccountOut.model_validate(account))


@auth.get("/menus", summary="当前账号菜单（RBAC ∩ License）")
def menus(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_menus(db, account))
