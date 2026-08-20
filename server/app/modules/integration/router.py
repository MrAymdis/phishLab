"""系统集成路由（Webhook / SIEM）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.audit import record_audit
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service
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


@webhooks.put("", summary="保存 Webhook 主配置（secret 加密入库）",
              dependencies=[Depends(require_perm("settings:manage"))])
def save_webhook(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.save_config(db, payload, operator_id=account.id)
    record_audit(
        db, account=account, module="integration", action="save_webhook",
        target_type="webhook_config", detail={"im_type": payload.get("im_type"),
                                              "event_types": payload.get("event_types") or []},
    )
    return resp.ok(list_webhooks(db))


@webhooks.post("/test", summary="Webhook 连通性测试（真实发送一条）",
               dependencies=[Depends(require_perm("settings:manage"))])
def test_webhook(payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    result = service.test_webhook(db, payload)
    record_audit(
        db, account=account, module="integration", action="test_webhook",
        target_type="webhook_config", detail={"ok": result.get("ok"), "status": result.get("status")},
    )
    return resp.ok(result)


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
