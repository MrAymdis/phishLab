from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.db.session import get_db

from . import service

overview = APIRouter(prefix="/api/v1/overview", tags=["数据概览"], dependencies=[Depends(get_current_account)])
reports = APIRouter(prefix="/api/v1/reports", tags=["数据报表"], dependencies=[Depends(get_current_account)])
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


@reports.get("/trend", summary="综合趋势（跨演练 + 场景）")
def trend_report(range: str = Query("quarter", alias="range"),
                 account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.trend_report(db, account, range))


@reports.get("/personal/{uid}", summary="员工个人安全档案")
def personal_report(uid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.personal_report(db, account, uid))


@reports.post("/export", summary="异步导出报表（Excel/PDF）")
def export(kind: str, params: dict, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"task_id": service.export_report(db, account, kind, params)})
