"""PhishLab 核心平台服务入口。"""
import importlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core import response as resp
from app.core.config import settings
from app.core.errors import BizError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("phishlab")

# 有管理端路由的业务模块（tracking 仅模型，无路由）
ROUTED_MODULES = (
    "account", "rbac", "org", "campaign", "template", "channel", "training",
    "report", "analytics", "ai", "openapi_mod", "integration", "license", "settings",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PhishLab server starting, env=%s", settings.env)
    yield
    logger.info("PhishLab server stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="钓鱼演练平台管理端 API（设计见《架构设计方案.md》）",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO(上线前)：收紧为前端域名白名单
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(BizError)
    async def biz_error_handler(request, exc: BizError):
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.get("/api/v1/health", tags=["系统"])
    def health():
        return resp.ok({"status": "up", "env": settings.env, "app": settings.app_name})

    # 平台静态资源（Logo 等上传文件）；no-cache 保证替换后不被浏览器缓存
    static_path = Path(settings.static_dir).resolve()
    static_path.mkdir(parents=True, exist_ok=True)

    @app.api_route("/static/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def static_files(file_path: str):
        target = (static_path / file_path).resolve()
        # 路径穿越防护：目标必须位于静态目录内
        if static_path not in target.parents or not target.is_file():
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(str(target), headers={"Cache-Control": "no-cache"})

    for name in ROUTED_MODULES:
        router_mod = importlib.import_module(f"app.modules.{name}.router")
        for router in router_mod.routers:
            app.include_router(router)

    return app


app = create_app()
