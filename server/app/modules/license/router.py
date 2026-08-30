from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service
from .fingerprint import get_machine_code

lic = APIRouter(prefix="/api/v1/license", tags=["系统设置-授权"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/settings"))])
routers = [lic]


class ActivateRequest(BaseModel):
    license_text: str  # .lic 授权文件内容（JSON 文本，验签 + 机器码绑定）


@lic.get("", summary="授权状态概览（配额进度 + 部署绑定）")
def status(db: Session = Depends(get_db)):
    return resp.ok(service.get_status(db))


@lic.get("/machine-code", summary="本机机器码（激活时提交给供应商绑定）")
def machine_code():
    return resp.ok({"machine_code": get_machine_code()})


@lic.post("/activate", summary="授权激活（粘贴 .lic 文件内容）", dependencies=[Depends(require_perm("license:manage"))])
def activate(req: ActivateRequest, db: Session = Depends(get_db)):
    return resp.ok(service.activate_offline(db, req.license_text.encode("utf-8")))


@lic.post("/offline-import", summary="授权激活（上传 .lic 文件）", dependencies=[Depends(require_perm("license:manage"))])
async def offline_import(file: UploadFile, db: Session = Depends(get_db)):
    content = await file.read()
    return resp.ok(service.activate_offline(db, content))
