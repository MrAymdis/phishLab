"""平台设置服务：跨模块统一读取 KV 配置。

按开发约定，模块间只经 service 层调用——其他模块需要平台参数时
通过 get_setting 取值，禁止直接查 platform_setting 表。
"""
from .models import PlatformSetting


def get_setting(db, key: str, default=None):
    """读取单个平台设置；未配置或值为 None 时返回 default。"""
    row = db.get(PlatformSetting, key)
    if row is None or row.setting_value is None:
        return default
    return row.setting_value
