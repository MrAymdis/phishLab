"""系统集成路由（Webhook / SIEM）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.db.session import get_db

from .models import SiemConfig, WebhookConfig

webhooks = APIRouter(prefix="/api/v1/webhooks", tags=["系统设置-集成"], dependencies=[Depends(get_current_account)])
siem = APIRouter(prefix="/api/v1/siem", tags=["系统设置-集成"], dependencies=[Depends(get_current_account)])
routers = [webhooks, siem]


@webhooks.get("", summary="Webhook 配置列表")
def list_webhooks(db: Session = Depends(get_db)):
    rows = db.scalars(select(WebhookConfig)).all()
    return resp.ok([
        {
            "id": w.id,
            "name": w.name,
            "im_type": w.im_type,
            "url": w.url,
            "event_types": w.event_types or [],
            "enabled": w.enabled,
        }
        for w in rows  # 注意：secret_enc 永不回传
    ])


@siem.get("", summary="SIEM Syslog 推送配置")
def get_siem(db: Session = Depends(get_db)):
    row = db.scalar(select(SiemConfig).order_by(SiemConfig.id.desc()))
    if row is None:
        return resp.ok({"host": "", "port": 514, "protocol": "udp", "format": "cef",
                        "event_types": [], "enabled": 0})
    return resp.ok({
        "host": row.host,
        "port": row.port,
        "protocol": row.protocol,
        "format": row.format,
        "event_types": row.event_types or [],
        "enabled": row.enabled,
    })
