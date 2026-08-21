"""平台基础参数路由（logo/名称/版权/留存天数/免责声明/AI开关）。

注：邮件追踪（像素/链接/附件）由模板级 track_pixel/track_link/track_attach 控制，
追踪域名来自演练绑定的 PhishDomain，此处不再维护全局追踪配置。
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.audit import record_audit
from app.core.config import settings as app_settings
from app.core.deps import get_current_account, require_perm
from app.core.errors import BizError, ErrorCode
from app.db.session import get_db

from .models import PlatformSetting

settings = APIRouter(prefix="/api/v1/settings", tags=["系统设置"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/settings"))])
public = APIRouter(prefix="/api/v1/settings", tags=["系统设置"])  # 无鉴权：登录页品牌展示
routers = [settings, public]

_DEFAULTS = {
    "name": "企业防钓鱼演练平台",
    "logo": "",
    "copyright": "© 2026 公司信息安全部 版权所有",
    "icp": "",
    "drill_domain": "drill.phishlab.cn",
    "retention_drill": "180d",
    "retention_behavior": "180d",
    "retention_log": "1y",
    "retention_days": "180",
    "disclaimer": "",
    "ai_switches": "{}",
    "compliance_confirm": "0",
}


@public.get("/public", summary="公开品牌信息（无鉴权：登录页名称/Logo/版权/备案）")
def public_brand(db: Session = Depends(get_db)):
    data = dict(_DEFAULTS)
    rows = db.scalars(
        select(PlatformSetting).where(
            PlatformSetting.setting_key.in_(["name", "logo", "copyright", "icp"])
        )
    ).all()
    for row in rows:
        data[row.setting_key] = row.setting_value
    return resp.ok({
        "name": data.get("name") or _DEFAULTS["name"],
        "logo": data.get("logo") or "",
        "copyright": data.get("copyright") or "",
        "icp": data.get("icp") or "",
    })


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
    # 取证操作密码只回显"是否已配置"，不暴露哈希
    if data.get("reveal_operation_pwd"):
        data["reveal_operation_pwd"] = "1"
    return resp.ok(data)


@settings.post("/logo", summary="上传平台 Logo（覆盖保存，/static 挂载访问）",
               dependencies=[Depends(require_perm("settings:manage"))])
async def upload_logo(file: UploadFile = File(...), account=Depends(get_current_account),
                      db: Session = Depends(get_db)):
    content = await file.read()
    if not content:
        raise BizError(ErrorCode.PARAM_INVALID, "Logo 文件为空")
    if len(content) > 512 * 1024:
        raise BizError(ErrorCode.PARAM_INVALID, "Logo 不能超过 512KB")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
        ext = ".png"
    filename = f"logo{ext}"
    static_path = Path(app_settings.static_dir)
    static_path.mkdir(parents=True, exist_ok=True)
    (static_path / filename).write_bytes(content)

    url = f"/static/{filename}"
    row = db.get(PlatformSetting, "logo")
    if row is None:
        db.add(PlatformSetting(setting_key="logo", setting_value=url, updated_by=account.id))
    else:
        row.setting_value = url
        row.updated_by = account.id
    db.commit()
    record_audit(
        db, account=account, module="settings", action="upload_logo",
        target_type="platform_setting", target_id="logo",
        detail={"logo": url, "size": len(content)},
    )
    return resp.ok({"logo": url})


@settings.put("", summary="批量更新平台参数（写审计）", dependencies=[Depends(require_perm("settings:manage"))])
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
        # 取证操作密码：只存 PBKDF2 哈希（不存原文/可逆密文），仅可验证不可还原
        if key == "reveal_operation_pwd" and value:
            from app.core.security import hash_password

            value = hash_password(str(value))
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
