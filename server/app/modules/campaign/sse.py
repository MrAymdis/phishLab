"""演练详情 SSE 实时推送：初始快照 + Redis pub/sub 订阅 → 心跳保活。

数据链路：追踪接口 → Redis Stream(evt:stream) → Worker 消费者落库并 publish
到 campaign_evt:{cid} → 本模块订阅后经 EventSourceResponse 推送给前端。
"""
import asyncio
import json
import logging
import time

import redis

from app.core.config import settings

logger = logging.getLogger("phishlab.sse")

# 心跳间隔（秒）：代理/浏览器保活，同时兜底推送积压
_HEARTBEAT_SEC = 15


def _frame(type_: str, data: dict) -> dict:
    return {"event": "message", "data": json.dumps({"type": type_, "data": data}, ensure_ascii=False)}


async def campaign_event_stream(db, account, campaign_id: int):
    """SSE 生成器：先推快照，再订阅 Redis 事件持续推送；客户端断开即结束。"""
    from . import service

    # 初始快照：数据权限过滤复用 dashboard/timeline 服务（与页面首次加载一致）
    try:
        dash = service.dashboard(db, account, campaign_id)
        tl = service.timeline(db, account, campaign_id, 1, 50)
    except Exception as err:  # 演练不存在/无权访问：推错误帧后结束
        yield _frame("error", {"message": str(err)})
        db.close()
        return
    # 快照数据就绪立即释放 DB 会话：SSE 长连接（可能数小时）不再占用连接池——
    # 此前每个挂起的 SSE 占 1 个连接（池上限 15），反复刷新会耗尽连接池卡死全部接口
    db.close()
    yield _frame("snapshot", {
        "dashboard": dash,
        "timeline": tl["list"],
        "timeline_total": tl["total"],
    })

    r = redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"campaign_evt:{campaign_id}"
    try:
        pubsub.subscribe(channel)
        last_beat = time.monotonic()
        while True:
            # 非阻塞轮询订阅消息（不能阻塞事件循环）
            msg = pubsub.get_message(ignore_subscribe_messages=True)
            if msg and msg.get("type") == "message":
                try:
                    payload = json.loads(msg["data"])
                except (json.JSONDecodeError, TypeError):
                    payload = {}
                frame_type = payload.get("type")
                if frame_type in ("event", "stats", "alert"):
                    yield _frame(frame_type, payload.get("data", {}))
            if time.monotonic() - last_beat >= _HEARTBEAT_SEC:
                yield _frame("heartbeat", {"t": int(time.time())})
                last_beat = time.monotonic()
            await asyncio.sleep(0.5)
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass
