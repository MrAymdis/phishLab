# PhishLab 钓鱼演练平台

企业级授权钓鱼演练系统：发送 → 追踪 → 中招教育 → 培训闭环 → 报表分析。

| 文档 | 说明 |
|---|---|
| [架构设计方案.md](./架构设计方案.md) | 前端/后端/数据库完整架构、DDL、状态机、分期路线 |
| [CLAUDE.md](./CLAUDE.md) | 开发约定、术语表、安全红线（AI 辅助开发入口） |
| [前端功能需求/](./前端功能需求/) | 功能需求总纲 + 11 个页面原型（设计基准） |

## 目录

- `web/` — 前端 Vue3 SPA（待建）
- `server/` — 后端 Python（FastAPI + Celery），见 [server/README.md](./server/README.md)
- `deploy/` — docker-compose / Dockerfile / nginx 配置

## 快速开始（后端）

```bash
cd server
cp .env.example .env
pip install fastapi "uvicorn[standard]" sqlalchemy alembic pymysql pydantic-settings \
    redis celery httpx sse-starlette pyjwt cryptography aiosmtplib dnspython minio \
    openpyxl python-multipart pytest email-validator
alembic upgrade head              # 建表
python scripts/seed_admin.py      # admin / PhishLab@2026
uvicorn app.main:app --reload --port 8080
# 打开 http://127.0.0.1:8080/docs
```

> ⚠️ 本平台仅可用于对签约客户自有员工、且取得书面授权的安全演练。
