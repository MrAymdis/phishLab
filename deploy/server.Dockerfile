FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv/phishlab

# 先拷依赖清单与离线 wheel（vendor/wheels 随发布包携带；本地命中即用，未命中回源 PyPI）
COPY server/pyproject.toml server/README.md server/
COPY server/vendor/wheels/ server/vendor/wheels/

RUN pip install --find-links=server/vendor/wheels \
    fastapi "uvicorn[standard]" sqlalchemy alembic pymysql cryptography \
    pydantic pydantic-settings email-validator redis celery httpx sse-starlette \
    pyjwt aiosmtplib dnspython exchangelib minio openpyxl python-multipart \
    sqlglot qrcode pillow pytest

# 再拷源码
COPY server/ server/

EXPOSE 8080 8081 8082
