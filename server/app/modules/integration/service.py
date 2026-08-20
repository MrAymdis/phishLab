"""Webhook 告警推送：配置保存（secret AES-GCM 加密）+ 事件触发推送 + 连通性测试。

推送语义：调用方（演练启动/终止、高危中招消费者、举报入库）以 event_type 触发，
配置中 enabled=1 且 event_types 命中才推送；失败仅记日志，绝不阻断主流程。
"""
import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import encrypt_secret

logger = logging.getLogger("phishlab.integration")

WEBHOOK_TIMEOUT = 5.0

# 事件类型 → 中文标签（消息文案用）
_EVENT_LABEL = {
    "campaign_start": "演练开始",
    "campaign_end": "演练结束",
    "high_risk": "高危中招",
    "report": "员工举报",
}


def save_config(db: Session, payload: dict, operator_id: int) -> None:
    """保存主配置（覆盖首条；无配置则新建）。secret 仅当非空时更新（留空不改）。"""
    from .models import WebhookConfig

    row = db.scalar(select(WebhookConfig).order_by(WebhookConfig.id).limit(1))
    if row is None:
        row = WebhookConfig(
            name=payload.get("name") or "安全告警推送",
            im_type=payload.get("im_type") or "wecom",
            url=payload.get("url") or "",
            event_types=payload.get("event_types") or [],
            enabled=1 if payload.get("enabled") else 0,
        )
        db.add(row)
    else:
        row.name = payload.get("name") or row.name
        row.im_type = payload.get("im_type") or row.im_type
        row.url = payload.get("url") or row.url
        row.event_types = payload.get("event_types") or []
        row.enabled = 1 if payload.get("enabled") else 0
    secret = (payload.get("secret") or "").strip()
    if secret:
        # 红线：webhook 签名密钥 AES-GCM 加密入库，接口永不回显
        row.secret_enc = encrypt_secret(secret)
    db.commit()


def notify_webhooks(db: Session, event_type: str, detail: dict) -> None:
    """事件推送入口：命中 enabled + event_types 的配置逐条发送。

    调用方在业务提交后调用（发送失败仅告警日志，不影响演练/举报主流程）。
    """
    from .models import WebhookConfig

    rows = db.scalars(
        select(WebhookConfig).where(WebhookConfig.enabled == 1)
    ).all()
    for w in rows:
        if event_type not in (w.event_types or []):
            continue
        payload = _build_payload(w.im_type, event_type, detail)
        try:
            httpx.post(w.url, json=payload, timeout=WEBHOOK_TIMEOUT)
        except Exception as e:  # 推送失败不阻断业务
            logger.warning("webhook push failed cfg=%s event=%s: %s", w.id, event_type, e)


def test_webhook(db: Session, payload: dict) -> dict:
    """连通性测试：按提交的配置发一条测试消息，返回 HTTP 状态。"""
    url = (payload.get("url") or "").strip()
    im_type = payload.get("im_type") or "wecom"
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "status": 0, "message": "URL 必须为 http/https"}
    body = _build_payload(im_type, "test", {"message": "PhishLab 告警推送连通性测试"})
    try:
        resp = httpx.post(url, json=body, timeout=WEBHOOK_TIMEOUT)
        ok = resp.status_code < 400
        return {"ok": ok, "status": resp.status_code, "message": "推送成功" if ok else f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "status": 0, "message": str(e)}


def _build_payload(im_type: str, event_type: str, detail: dict) -> dict:
    """按 IM 类型构造消息体（企业微信/钉钉/飞书/自定义 JSON）。"""
    title = _EVENT_LABEL.get(event_type, event_type)
    lines = [f"【{title}】PhishLab 告警"]
    for k, v in (detail or {}).items():
        if v is not None and v != "":
            lines.append(f"{k}：{v}")
    text = "\n".join(lines)
    if im_type == "wecom":
        return {"msgtype": "text", "text": {"content": text}}
    if im_type == "dingtalk":
        return {"msgtype": "text", "text": {"content": text}}
    if im_type == "feishu":
        return {"msg_type": "text", "content": {"text": text}}
    return {"text": text, "event": event_type, "detail": detail or {}}
