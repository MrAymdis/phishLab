from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service

overview = APIRouter(prefix="/api/v1/overview", tags=["数据概览"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/dashboard"))])
reports = APIRouter(prefix="/api/v1/reports", tags=["数据报表"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/reports"))])
routers = [overview, reports]


@overview.get("/metrics", summary="概览指标（近7天/本月/本季度联动）")
def metrics(range: str = Query("month", alias="range", description="7d/month/quarter"),
            account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.overview_metrics(db, account, range))


@reports.get("/campaign/{cid}", summary="单次演练报表（漏斗+明细）")
def campaign_report(cid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.campaign_report(db, account, cid))


@reports.get("/department", summary="部门横向对比")
def department_report(range: str = Query("month", alias="range"),
                      account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.department_report(db, account, range))


@reports.get("/department/{dept_id}/persons", summary="部门内人员明细（参与次数/中招率/风险）")
def dept_persons(dept_id: int, range: str = Query("month", alias="range"),
                 account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.dept_persons_report(db, account, dept_id, range))


@reports.get("/trend", summary="综合趋势（跨演练 + 场景）")
def trend_report(range: str = Query("quarter", alias="range"),
                 account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.trend_report(db, account, range))


@reports.get("/personal/{uid}", summary="员工个人安全档案")
def personal_report(uid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.personal_report(db, account, uid))


class ReportExport(BaseModel):
    """导出请求：kind 文件格式，scope 报表范围，其余参数按 scope 可选。"""
    kind: str = Field(description="excel / pdf")
    scope: str = Field(description="campaign / department / trend / personal / batch")
    campaign_id: int | None = None
    campaign_ids: list[int] | None = None  # scope=batch：多演练拼接导出
    dept_id: int | None = None
    user_id: int | None = None
    range: str = Field("month", description="时间范围 7d/month/quarter/year")


@reports.post("/export", summary="导出报表文件流（Excel/PDF，同步生成）")
def export(payload: ReportExport, account=Depends(get_current_account), db: Session = Depends(get_db)):
    content, filename, media_type = service.export_report(
        db, account, payload.kind, payload.model_dump())
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
