"""平台基础参数路由（logo/名称/版权/像素开关/留存天数/免责声明/AI开关）。"""
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.audit import record_audit
from app.core.deps import get_current_account
from app.db.session import get_db

from .models import PlatformSetting

settings = APIRouter(prefix="/api/v1/settings", tags=["系统设置"], dependencies=[Depends(get_current_account)])
routers = [settings]

_DEFAULTS = {
    "name": "企业防钓鱼演练平台",
    "logo": "",
    "copyright": "© 2026 公司信息安全部 版权所有",
    "icp": "",
    "pixel_enabled": "1",
    "track_domain": "track.drill-domain.com",
    "link_expire": "campaign",
    "redirect_url": "",
    "retention_drill": "180d",
    "retention_behavior": "180d",
    "retention_log": "1y",
    "retention_days": "180",
    "disclaimer": "",
    "ai_switches": "{}",
    "compliance_confirm": "0",
}


def _decode(value: str | None):
    """JSON 值解码：以 {/[ 开头按 JSON 解析，否则原样返回。"""
    if value is None:
        return None
    s = value.strip()
    if s[:1] in ("{", "["):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return value
    return value


@settings.get("", summary="平台基础参数")
def get_settings(db: Session = Depends(get_db)):
    data = dict(_DEFAULTS)
    for row in db.scalars(select(PlatformSetting)).all():
        data[row.setting_key] = _decode(row.setting_value)
    return resp.ok(data)


@settings.put("", summary="批量更新平台参数（写审计）")
def update_settings(
    payload: dict,
    request: Request,
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif value is not None and not isinstance(value, str):
            value = str(value)
        row = db.get(PlatformSetting, key)
        if row is None:
            row = PlatformSetting(setting_key=key, setting_value=value)
            db.add(row)
        else:
            row.setting_value = value
        row.updated_by = account.id
    db.commit()
    record_audit(
        db, account=account, module="settings", action="update",
        target_type="platform_setting",
        detail={"keys": list(payload.keys())},
        ip=request.client.host if request.client else None,
    )
    return resp.ok(get_settings(db))
