from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.db.session import get_db

from . import service

open_apps = APIRouter(prefix="/api/v1/open-apps", tags=["API开放平台"], dependencies=[Depends(get_current_account)])
gateway = APIRouter(prefix="/openapi/v1", tags=["API开放平台-网关"])
routers = [open_apps, gateway]


class AppCreate(BaseModel):
    name: str
    description: str | None = None
    scopes: list[str] = []  # campaign/user/template/report/mail_report/system
    ip_whitelist: list[str] = []
    callback_url: str | None = None
    rate_limit: int = 60


class TokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    app_id: str
    app_secret: str


@open_apps.get("", summary="应用列表")
def list_apps(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_apps(db, account))


@open_apps.post("", summary="创建应用（AppID/AppSecret）")
def create_app(payload: AppCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.create_app(db, account, payload.model_dump()))


@gateway.post("/oauth/token", summary="client_credentials 换取 access_token")
def token(req: TokenRequest, db: Session = Depends(get_db)):
    return resp.ok(service.issue_token(db, req.app_id, req.app_secret))
