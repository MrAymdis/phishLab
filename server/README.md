# PhishLab Server（后端）

FastAPI 模块化单体 + Celery Worker。完整设计见仓库根目录《架构设计方案.md》。

## 快速开始

```bash
cp .env.example .env            # 按需修改数据库/Redis 连接
poetry install                  # 或 pip install -e .
poetry run alembic upgrade head # 建表
python scripts/seed_admin.py    # 初始化超管账号 admin / PhishLab@2026
poetry run uvicorn app.main:app --reload --port 8080
```

依赖中间件一键启动：`docker compose -f ../deploy/docker-compose.yml up -d mysql redis minio`

## 进程入口

| 进程 | 命令 | 说明 |
|---|---|---|
| 核心服务 | `uvicorn app.main:app --port 8080` | 管理端 API `/api/v1/**` |
| 投递 Worker | `celery -A worker worker` | 批次发送 / 重试 |
| 定时调度 | `celery -A worker beat` | 批次派发 / DNS 巡检 / 汇总 / 留存清理（单实例） |
| 追踪服务 | `uvicorn track.main:app --port 8081` | 独立部署，追踪域名 |
| 落地页 | `uvicorn landing.main:app --port 8082` | 独立部署，演练域名 |

## 结构约定

- `app/modules/<模块>/{models,schemas,service,router}.py`：模块间只经 service 层调用；
- 未实现的端点统一抛 `BizError(ErrorCode.NOT_IMPLEMENTED)`，接口面在 `/docs` 可见；
- 结构变更：改 models → `alembic revision --autogenerate -m "xxx"` → 人工审查后 `upgrade`；
- 敏感配置字段一律 `*_enc`（AES-GCM），见 `app/core/security.py`。
