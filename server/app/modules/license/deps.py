"""License 功能门控依赖：路由器级 fail-closed。

菜单隐藏只是导航层约束；拷贝部署后绕过前端直调 API 也必须被拒绝，
因此旗舰专属功能（openapi/payload 等）的路由需挂此依赖，与 feature_enabled 同一裁决源。
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.db.session import get_db

from .service import feature_enabled


def require_license_feature(feature: str):
    def dep(db: Session = Depends(get_db)):
        if not feature_enabled(db, feature):
            raise BizError(ErrorCode.PERM_DENIED,
                           f"当前授权不包含该功能（{feature}），需升级版本后使用")
    return dep
