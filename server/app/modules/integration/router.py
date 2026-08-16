"""系统集成路由（Webhook / SIEM）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.core.errors import BizError, ErrorCode
from app.db.session import get_db

webhooks = APIRouter(prefix="/api/v1/webhooks", tags=["系统设置-集成"], dependencies=[Depends(get_current_account)])
siem = APIRouter(prefix="/api/v1/siem", tags=["系统设置-集成"], dependencies=[Depends(get_current_account)])
routers = [webhooks, siem]


@webhooks.get("", summary="Webhook 配置列表")
def list_webhooks(db: Session = Depends(get_db)):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


@siem.get("", summary="SIEM Syslog 推送配置")
def get_siem(db: Session = Depends(get_db)):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
