"""平台基础参数路由（logo/名称/版权/像素开关/留存天数/免责声明/AI开关）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.core.errors import BizError, ErrorCode
from app.db.session import get_db

settings = APIRouter(prefix="/api/v1/settings", tags=["系统设置"], dependencies=[Depends(get_current_account)])
routers = [settings]


@settings.get("", summary="平台基础参数")
def get_settings(db: Session = Depends(get_db)):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


@settings.put("", summary="批量更新平台参数（写审计）")
def update_settings(payload: dict, db: Session = Depends(get_db)):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
