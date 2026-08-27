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


def validate_base_url(value: str, *, request_host: str | None = None, key: str = "base_url") -> str:
    """追踪/落地域基础 URL 校验（设置页与演练级共用）：

    http(s)://域名[:端口]，无路径/查询串；传 request_host 时校验不与主平台同域（红线 3）；
    生产环境强制 https。返回规范化值（去尾部 /）；空串 = 未配置。
    """
    from urllib.parse import urlparse

    from app.core.config import settings
    from app.core.errors import BizError, ErrorCode

    if not value:
        return ""
    parsed = urlparse(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise BizError(ErrorCode.PARAM_INVALID,
                       f"{key} 格式非法：需为 http(s)://域名[:端口]，不含路径")
    if request_host and parsed.hostname.lower() == request_host.lower():
        raise BizError(ErrorCode.PARAM_INVALID,
                       f"{key} 不能与主平台同域名（红线 3：追踪/落地域必须与主平台域名隔离）")
    if settings.env != "dev" and parsed.scheme != "https":
        raise BizError(ErrorCode.PARAM_INVALID, f"{key} 生产环境必须使用 https")
    return value.rstrip("/")


def resolve_track_urls(db, campaign=None) -> tuple[str, str]:
    """解析追踪/落地域基础 URL：演练级覆盖 > 平台设置（设置页前端配置）> dev 端口直连 > .env。

    返回 (track_base, landing_base)：
    - campaign.track_base_url + landing_base_url 成对配置 → 演练级覆盖（域名轮换用）；
    - 设置页配置了 track_base_url + landing_base_url（成对生效）→ 直接使用；
    - env=dev 且未配置 → ("", "")，调用方沿用 http://{演练域名}:{landing_port} 直连（本地联调）；
    - 其他环境未配置 → .env 的 TRACK_BASE_URL / LANDING_BASE_URL。
    """
    from app.core.config import settings

    if campaign is not None:
        track = (campaign.track_base_url or "").strip().rstrip("/")
        landing = (campaign.landing_base_url or "").strip().rstrip("/")
        if track and landing:
            return track, landing
    track = (get_setting(db, "track_base_url", "") or "").strip().rstrip("/")
    landing = (get_setting(db, "landing_base_url", "") or "").strip().rstrip("/")
    if track and landing:
        return track, landing
    if settings.env == "dev":
        return "", ""
    return settings.track_base_url.rstrip("/"), settings.landing_base_url.rstrip("/")
