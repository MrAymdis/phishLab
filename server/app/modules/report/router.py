from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.core.pagination import page_params
from app.db.session import get_db

from . import service

mail_reports = APIRouter(prefix="/api/v1/mail-reports", tags=["邮件举报"], dependencies=[Depends(get_current_account)])
plugin = APIRouter(prefix="/report/v1", tags=["邮件举报-插件"])  # 插件端点,独立鉴权(TODO)
routers = [mail_reports, plugin]


class ClassifyRequest(BaseModel):
    classification: str  # drill/real_phishing/false_positive/spam
    remark: str | None = None


class PluginReport(BaseModel):
    channel: str = "outlook_plugin"
    reporter_email: str | None = None
    message_id: str | None = None
    from_addr: str | None = None
    subject: str | None = None
    headers: str | None = None
    eml_base64: str | None = None


@mail_reports.get("", summary="举报列表（分类筛选）")
def list_reports(
    classification: str | None = None,
    paging: tuple[int, int] = Depends(page_params),
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    page, page_size = paging
    return resp.ok(service.list_reports(db, account, classification=classification, page=page, page_size=page_size))


@mail_reports.post("/{rid}/classify", summary="人工研判", dependencies=[Depends(require_perm("report:classify"))])
def classify(rid: int, req: ClassifyRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.classify(db, account, rid, req.classification, req.remark))


@plugin.post("/mail", summary="举报插件上报（Outlook/Webmail）")
def plugin_report(payload: PluginReport, db: Session = Depends(get_db)):
    # TODO: 插件独立鉴权（硬件指纹/签名）
    return resp.ok({"id": service.ingest_from_plugin(db, payload.model_dump())})
