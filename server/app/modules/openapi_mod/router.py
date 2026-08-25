import time

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.core.errors import BizError
from app.db.session import get_db
from app.modules.campaign.schemas import CampaignCreate

from . import biz, service

open_apps = APIRouter(prefix="/api/v1/open-apps", tags=["API开放平台"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/openapi"))])
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


def require_scope(scope: str):
    """开放平台网关依赖：鉴权（JWT 验签 → 应用状态 → IP 白名单 → scope → 限流）
    + 调用审计落库（OpenApiLog，不记请求/响应正文）。

    注意：必须是 FastAPI 原生 async generator（yield）依赖——asynccontextmanager
    包装的函数 FastAPI 不识别为依赖，会原样把 context manager 传给端点。
    """

    async def dep(request: Request, db: Session = Depends(get_db)):
        app = service.authenticate(request, db, scope)
        started = time.monotonic()
        try:
            yield app
        except BizError as exc:
            service.log_call(db, app, request, exc.http_status, started, str(exc.message))
            raise
        except Exception:
            service.log_call(db, app, request, 500, started, "internal error")
            raise
        else:
            service.log_call(db, app, request, 200, started, None)

    return dep


@open_apps.get("", summary="应用列表")
def list_apps(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_apps(db, account))


@open_apps.post("", summary="创建应用（AppID/AppSecret）", dependencies=[Depends(require_perm("openapi:manage"))])
def create_app(payload: AppCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.create_app(db, account, payload.model_dump()))


@gateway.post("/oauth/token", summary="client_credentials 换取 access_token")
def token(req: TokenRequest, db: Session = Depends(get_db)):
    return resp.ok(service.issue_token(db, req.app_id, req.app_secret))


# ---------- campaign scope ----------


@gateway.get("/campaigns", summary="演练列表（含实时统计）")
def list_campaigns(
    status: str | None = Query(None, description="draft/scheduled/sending/running/paused/completed/terminated"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _app=Depends(require_scope("campaign")),
):
    return resp.ok(biz.list_campaigns(db, page=page, page_size=page_size, status=status))


@gateway.get("/campaigns/{cid}", summary="演练详情（含中招统计）")
def get_campaign(cid: int, db: Session = Depends(get_db), _app=Depends(require_scope("campaign"))):
    return resp.ok(biz.get_campaign(db, cid))


@gateway.post("/campaigns", summary="创建演练草稿（auth_confirmed 必填为 true，红线 4）")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db),
                    app=Depends(require_scope("campaign"))):
    return resp.ok({"id": biz.create_campaign(db, app, payload)})


@gateway.get("/campaigns/{cid}/targets", summary="演练目标明细（含中招状态）")
def list_targets(
    cid: int,
    victim_only: bool = Query(False, description="仅中招（提交或附件运行）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _app=Depends(require_scope("campaign")),
):
    return resp.ok(biz.list_targets(db, cid, page=page, page_size=page_size, victim_only=victim_only))


@gateway.get("/campaigns/{cid}/report", summary="演练结果报表（指标卡/漏斗/中招明细/日趋势）")
def campaign_report(cid: int, db: Session = Depends(get_db), _app=Depends(require_scope("campaign"))):
    return resp.ok(biz.campaign_report(db, cid))


# ---------- report scope ----------


@gateway.get("/reports/overview", summary="平台概览指标")
def overview(db: Session = Depends(get_db), _app=Depends(require_scope("report"))):
    return resp.ok(biz.overview(db))


@gateway.get("/reports/trend", summary="中招趋势（按天，victim=提交+附件运行）")
def trend(range_: str = Query("month", alias="range", description="7d/month/quarter"),
          db: Session = Depends(get_db), _app=Depends(require_scope("report"))):
    return resp.ok(biz.trend(db, range_))


@gateway.get("/reports/department", summary="部门中招对比")
def department_report(range_: str = Query("month", alias="range", description="7d/month/quarter"),
                      db: Session = Depends(get_db), _app=Depends(require_scope("report"))):
    return resp.ok(biz.department_report(db, range_))


# ---------- user scope ----------


@gateway.get("/users", summary="员工列表（含行为统计）")
def list_users(
    kw: str | None = None,
    dept_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _app=Depends(require_scope("user")),
):
    return resp.ok(biz.list_users(db, page=page, page_size=page_size, kw=kw, dept_id=dept_id))


@gateway.get("/users/{uid}", summary="员工详情（行为统计 + 最近行为事件）")
def get_user(uid: int, db: Session = Depends(get_db), _app=Depends(require_scope("user"))):
    return resp.ok(biz.get_user(db, uid))


# ---------- template scope ----------


@gateway.get("/templates", summary="邮件模板列表（只读）")
def list_templates(scene: str | None = Query(None, description="finance/hr/system/holiday/prize/security"),
                   db: Session = Depends(get_db), _app=Depends(require_scope("template"))):
    return resp.ok(biz.list_templates(db, scene))


@gateway.get("/templates/{tid}", summary="邮件模板详情（含正文）")
def get_template(tid: int, db: Session = Depends(get_db), _app=Depends(require_scope("template"))):
    return resp.ok(biz.get_template(db, tid))


# ---------- mail_report scope ----------


@gateway.get("/mail-reports", summary="举报列表（只读）")
def list_mail_reports(
    classification: str | None = Query(None, description="pending/drill/real_phishing/false_positive/spam"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _app=Depends(require_scope("mail_report")),
):
    return resp.ok(biz.list_mail_reports(db, page=page, page_size=page_size, classification=classification))


# ---------- system scope ----------


@gateway.get("/system/info", summary="平台基础信息")
def system_info(db: Session = Depends(get_db), _app=Depends(require_scope("system"))):
    return resp.ok(biz.system_info(db))
