FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv/phishlab

# 先拷依赖清单利用缓存（package-mode=false：pip 只安装依赖）
COPY server/pyproject.toml server/README.md server/
RUN pip install --no-cache-dir ./server 2>/dev/null || pip install --no-cache-dir \
    fastapi "uvicorn[standard]" sqlalchemy alembic pymysql cryptography \
    pydantic pydantic-settings email-validator redis celery httpx sse-starlette \
    pyjwt aiosmtplib dnspython exchangelib minio openpyxl python-multipart pytest

# 再拷源码
COPY server/ server/

EXPOSE 8080 8081 8082
