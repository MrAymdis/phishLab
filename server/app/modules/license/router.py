from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.db.session import get_db

from . import service

lic = APIRouter(prefix="/api/v1/license", tags=["系统设置-授权"], dependencies=[Depends(get_current_account)])
routers = [lic]


class ActivateRequest(BaseModel):
    license_key: str


@lic.get("", summary="授权状态概览（配额进度）")
def status(db: Session = Depends(get_db)):
    return resp.ok(service.get_status(db))


@lic.post("/activate", summary="在线激活")
def activate(req: ActivateRequest, db: Session = Depends(get_db)):
    return resp.ok(service.activate_online(db, req.license_key))


@lic.post("/offline-import", summary="离线激活文件导入（.lic）")
async def offline_import(file: UploadFile, db: Session = Depends(get_db)):
    content = await file.read()
    return resp.ok(service.activate_offline(db, content))
