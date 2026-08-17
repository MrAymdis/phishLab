"""Celery Worker 包：暴露 app 供 `celery -A worker` 启动。"""
from .celery_app import celery_app as app  # noqa: F401
