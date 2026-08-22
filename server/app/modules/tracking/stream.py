"""追踪事件流：Track/落地页服务只 XADD Redis Stream（evt:stream），
由 Worker 消费者批量落库——禁止在 Track API 同步写 MySQL（CLAUDE.md 红线）。"""
import json
from datetime import datetime

import redis

from app.core.config import settings

EVENT_STREAM = "evt:stream"
EVENT_GROUP = "evt-consumers"
MAX_LEN = 10000  # 流裁剪上限，防止积压


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def resolve_landing_slug(token: str) -> str | None:
    """token → 演练落地页 slug（点击跳转 /t/{token} 用）。

    只读查询（红线：追踪侧禁止写 MySQL）；token 无效返回 None，调用方兜底。
    """
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.modules.campaign.models import Campaign, CampaignTarget
    from app.modules.template.models import LandingPage

    if not token:
        return None
    try:
        db = SessionLocal()
        try:
            target = db.scalar(select(CampaignTarget).where(CampaignTarget.token == token))
            if target is None:
                return None
            campaign = db.get(Campaign, target.campaign_id)
            if campaign is None or not campaign.landing_page_id:
                return None
            page = db.get(LandingPage, campaign.landing_page_id)
            return page.slug if page else None
        finally:
            db.close()
    except Exception:
        return None  # DB 异常回退兜底跳转，不阻断链路


def push_event(*, token: str, event_type: str, ip: str = "", ua: str = "",
               detail: dict | None = None) -> bool:
    """追加一条追踪事件（open/click/submit/report...）。token 未知也入流，消费端丢弃。"""
    try:
        r = _client()
        r.xadd(
            EVENT_STREAM,
            {
                "token": token,
                "event_type": event_type,
                "ip": ip or "",
                "ua": (ua or "")[:512],
                "detail": json.dumps(detail or {}, ensure_ascii=False),
                "ts": datetime.now().isoformat(),
            },
            maxlen=MAX_LEN,
            approximate=True,
        )
        return True
    except Exception:
        return False


def _ensure_group(r: redis.Redis):
    try:
        r.xgroup_create(EVENT_STREAM, EVENT_GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError:
        pass  # 组已存在


def read_pending(r: redis.Redis, count: int = 100) -> list[tuple[str, dict]]:
    """消费组读取（含重试未确认消息）：返回 [(event_id, fields), ...]。"""
    _ensure_group(r)
    events = []
    try:
        entries = r.xreadgroup(EVENT_GROUP, "phishlab-consumer", {EVENT_STREAM: ">"}, count=count)
        for _stream, msgs in entries:
            for msg_id, fields in msgs:
                events.append((msg_id, fields))
    except redis.exceptions.ResponseError:
        pass  # 空流
    # 补读未确认的旧消息（消费者重启后重放）
    try:
        pending = r.xreadgroup(EVENT_GROUP, "phishlab-consumer", {EVENT_STREAM: "0"}, count=count)
        for _stream, msgs in pending:
            for msg_id, fields in msgs:
                if (msg_id, fields) not in events:
                    events.append((msg_id, fields))
    except redis.exceptions.ResponseError:
        pass
    return events


def ack(r: redis.Redis, event_ids: list[str]):
    if event_ids:
        try:
            r.xack(EVENT_STREAM, EVENT_GROUP, *event_ids)
        except Exception:
            pass
