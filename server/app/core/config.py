"""应用配置：pydantic-settings，环境变量 > .env > 默认值。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PhishLab"
    env: str = "dev"
    secret_key: str = "change-me-to-a-random-secret-at-least-32-chars"

    database_url: str = (
        "mysql+pymysql://phishlab:phishlab@127.0.0.1:3306/phishlab?charset=utf8mb4"
    )
    redis_url: str = "redis://127.0.0.1:6379/0"

    jwt_expire_minutes: int = 720
    aes_key_b64: str = ""  # 留空时开发环境从 SECRET_KEY 派生（生产必须显式配置/KMS）

    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False

    # CORS 白名单：默认放开（开发）；生产收紧为前端域名（JSON 数组，如 ["https://admin.example.com"]）
    cors_origins: list[str] = ["*"]

    track_base_url: str = "https://t.phish-example.com"
    landing_base_url: str = "https://p.phish-example.com"
    # 落地页服务演示端口：开发机用 http://{演练域名}:{port}/p/{slug} 直连（hosts 映射域名后即可点击演示）
    landing_port: int = 8082

    # 平台静态资源目录（Logo 等上传文件，经 /static 挂载访问）
    static_dir: str = "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
