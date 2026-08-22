"""追踪服务（独立进程/独立域名部署）：1×1 像素、链接跳转、指纹接收。

事件统一写 Redis Stream `evt:stream`，由核心服务消费者批量落库 + 更新实时计数。
"""
import base64
import logging

import redis
from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phishlab.track")

app = FastAPI(title="PhishLab Track", docs_url=None)  # 边缘服务不暴露文档

# 1×1 透明 GIF
_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

_redis: redis.Redis | None = None


def _stream() -> redis.Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = redis.Redis.from_url(settings.redis_url)
            _redis.ping()
        except Exception:  # Redis 不可用时降级：只返回像素不记事件
            logger.exception("redis unavailable")
            _redis = None
    return _redis


def _emit(token: str, event_type: str, request: Request, **extra):
    r = _stream()
    if r is None:
        return
    payload = {
        "token": token,
        "event_type": event_type,
        "ip": request.client.host if request.client else "",
        "ua": (request.headers.get("user-agent") or "")[:512],
        **{k: str(v) for k, v in extra.items()},
    }
    try:
        r.xadd("evt:stream", payload, maxlen=100000)
    except Exception:
        logger.exception("xadd failed")


@app.get("/health")
def health():
    return {"status": "up"}


@app.get("/px/{token}.gif")
def pixel(token: str, request: Request):
    """打开追踪像素（事件去重由消费侧 60s 窗口处理）。TODO(二期)：pixel_degrade 演练配置判断。"""
    _emit(token, "open", request)
    return Response(content=_PIXEL, media_type="image/gif",
                    headers={"Cache-Control": "no-store"})


@app.get("/px/{token}.png")
def pixel_png(token: str, request: Request):
    """像素降级模式：正常尺寸图片替代 1×1 像素，同样记录 open 事件。"""
    from app.modules.tracking.stream import pixel_png_bytes

    _emit(token, "open", request)
    return Response(content=pixel_png_bytes(), media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@app.get("/t/{token}")
def redirect(token: str, request: Request):
    """链接点击跳转：token → 演练落地页 slug（只读查库）→ 记 click 事件 → 302。

    token 无效时兜底跳 placeholder 页（渲染默认登录卡片，无害）。
    """
    from app.modules.tracking.stream import resolve_landing_slug

    slug = resolve_landing_slug(token)
    if slug:
        _emit(token, "click", request)
    landing = f"{settings.landing_base_url}/p/{slug or 'placeholder'}"
    if slug:
        landing += f"?token={token}"
    return Response(status_code=302, headers={"Location": landing})
