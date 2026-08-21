from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service

email_templates = APIRouter(prefix="/api/v1/email-templates", tags=["素材模板"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/template"))])
landing_pages = APIRouter(prefix="/api/v1/landing-pages", tags=["素材模板"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/template"))])
attachments = APIRouter(prefix="/api/v1/attachments", tags=["素材模板"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/template"))])
qr_assets = APIRouter(prefix="/api/v1/qr-assets", tags=["素材模板"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/template"))])
routers = [email_templates, landing_pages, attachments, qr_assets]


class EmailTemplateCreate(BaseModel):
    name: str
    scene: str  # finance/hr/system/holiday/prize/security
    subject: str
    html_body: str
    source: str = "custom"
    # 追踪选项（投递时生效）
    track_pixel: bool = True
    track_link: bool = True
    track_attach: bool = False


class LandingPageCreate(BaseModel):
    name: str
    type: str  # mail_login/oa_login/pan_auth/custom/cloned
    html_content: str | None = None
    form_schema: dict | None = None


class CloneRequest(BaseModel):
    url: str
    name: str | None = None
    type: str | None = None  # mail_login/oa_login/pan_auth/custom/cloned


@email_templates.get("", summary="邮件模板列表")
def list_templates(scene: str | None = None, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_email_templates(db, account, scene))


@email_templates.post("", summary="新建邮件模板", dependencies=[Depends(require_perm("template:manage"))])
def create_template(payload: EmailTemplateCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_email_template(db, account, payload.model_dump())})


@email_templates.post("/{tid}/duplicate", summary="复制模板（生成副本）", dependencies=[Depends(require_perm("template:manage"))])
def duplicate_template(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.duplicate_email_template(db, account, tid)})


@email_templates.delete("/{tid}", summary="删除邮件模板（被演练引用时阻止）", dependencies=[Depends(require_perm("template:manage"))])
def delete_template(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_email_template(db, account, tid))


@email_templates.get("/{tid}", summary="邮件模板详情")
def get_template(tid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_email_template(db, tid))


@email_templates.put("/{tid}", summary="更新邮件模板", dependencies=[Depends(require_perm("template:manage"))])
def update_template(tid: int, payload: EmailTemplateCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.update_email_template(db, account, tid, payload.model_dump())
    return resp.ok({"id": tid})


@email_templates.post("/{tid}/test-send", summary="模板测试发送（默认 SMTP 通道真实投递，收件人白名单前端约束）",
                       dependencies=[Depends(require_perm("template:manage"))])
def test_send(tid: int, payload: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    to = [str(a).strip() for a in (payload.get("to") or []) if str(a).strip()]
    return resp.ok(service.test_send_template(db, account, tid, to))


@landing_pages.get("", summary="落地页列表")
def list_pages(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_landing_pages(db, account))


@landing_pages.get("/{pid}", summary="落地页详情")
def get_page(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_landing_page(db, pid))


@landing_pages.get("/{pid}/preview", summary="落地页预览（消毒后渲染，与线上 /p/{slug} 一致）")
def preview_page(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.get_landing_page_preview(db, pid))


@landing_pages.post("", summary="新建落地页", dependencies=[Depends(require_perm("template:manage"))])
def create_page(payload: LandingPageCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.create_landing_page(db, account, payload.model_dump())})


@landing_pages.put("/{pid}", summary="更新落地页", dependencies=[Depends(require_perm("template:manage"))])
def update_page(pid: int, payload: LandingPageCreate, account=Depends(get_current_account), db: Session = Depends(get_db)):
    service.update_landing_page(db, account, pid, payload.model_dump())
    return resp.ok({"id": pid})


@landing_pages.post("/{pid}/duplicate", summary="复制落地页（生成副本）", dependencies=[Depends(require_perm("template:manage"))])
def duplicate_page(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.duplicate_landing_page(db, account, pid)})


@landing_pages.delete("/{pid}", summary="删除落地页（被演练引用时阻止）",
                      dependencies=[Depends(require_perm("template:manage"))])
def delete_page(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_landing_page(db, account, pid))


@landing_pages.post("/clone", summary="URL 克隆工具（红线：仅限客户自有系统页面，全程审计）",
                    dependencies=[Depends(require_perm("template:manage"))])
def clone(payload: CloneRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"id": service.clone_url(db, account, payload.url, payload.name, payload.type)})


@attachments.get("", summary="附件载荷列表")
def list_attachments(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_attachments(db, account))


@qr_assets.get("", summary="二维码资产列表")
def list_qr(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_qr_assets(db, account))
