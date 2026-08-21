# CLAUDE.md

钓鱼演练平台（PhishLab）— 企业级网络安全钓鱼演练系统，"以演促练、教育为主、惩罚为辅"。

## 项目概述

面向企业客户的授权钓鱼演练平台：向目标员工投递模拟钓鱼邮件/短信 → 追踪打开/点击/提交行为 → 中招后即时教育 → 培训考试闭环 → 报表与风险画像分析。含 AI 助手、邮件举报、API 开放平台与 License 商业化授权。

**设计文档（开发前必读）**：
- 《架构设计方案.md》— 前端/后端/数据库完整架构、DDL、状态机、分期路线
- `前端功能需求/前端功能需求.md` — 功能需求总纲（11 个模块）
- `前端功能需求/*.html` — 11 个页面静态原型（视觉与交互的**唯一设计基准**，开发页面时先对照）

## 仓库结构（规划）

```
phishlab/
├── web/                  # 前端 Vue3 SPA（待建）
├── server/               # 后端 Python：FastAPI 模块化单体 + Celery Worker/Beat
│                         # + track(追踪服务入口) + landing(落地页服务入口)（待建）
├── deploy/               # docker-compose、Nginx 配置、域名证书说明
├── docs/                 # API 文档、部署手册、合规说明
├── 前端功能需求/          # 原型与需求（只读参考，勿改）
└── 架构设计方案.md
```

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | Vue 3 + TS + Vite + Element Plus + Pinia + Vue Router + ECharts 5 + wangEditor |
| 后端 | Python 3.11 + FastAPI + Uvicorn + SQLAlchemy 2.0 + Pydantic v2 + Celery(+Beat) |
| 存储 | MySQL 8 / Redis 7 / MinIO；ES 二期；迁移 Alembic |
| 集成 | aiosmtplib、exchangelib、dnspython、LangChain/httpx、openpyxl + WeasyPrint |

## 常用命令（工程建立后）

```bash
# 前端
cd web && pnpm install && pnpm dev        # 本地开发(0.0.0.0:5173，代理/api /static→8080)
pnpm build                                 # 产物 dist/

# 后端
cd server && poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080   # 核心服务（0.0.0.0 供局域网/容器访问）
poetry run celery -A worker worker -l info               # 投递引擎 Worker
poetry run celery -A worker beat                         # 定时调度(单实例)
poetry run alembic upgrade head                          # 数据库迁移
poetry run pytest

# 一键起依赖
docker compose -f deploy/docker-compose.yml up -d mysql redis minio
```

## 领域术语表

| 术语 | 英文/代码 | 含义 |
|---|---|---|
| 演练 | campaign | 一次钓鱼演练活动 |
| 演练对象/员工 | emp_user | 被演练的员工（与平台账号 sys_account 严格分离） |
| 中招 | submit | 在落地页提交了表单（最高危事件） |
| 落地页 | landing_page | 仿冒登录页等，托管在独立演练域名 `/p/{slug}` |
| 追踪令牌 | token | campaign_target 唯一令牌，贯穿像素/链接/落地页 |
| 伪装发件人 | sender_profile | 显示名/From/Reply-To/短信号 |
| 送达评分 | deliver_score | SPF30+DKIM30+DMARC20+MX10+黑名单10，0-100 |
| 举报 | mail_report | 员工通过插件上报可疑邮件 |
| 草稿审核 | ai_draft | AI 产出统一先草稿、人工确认后入库（硬约束） |

## 关键状态枚举

- campaign.status: `draft / scheduled / sending / running / paused / completed / terminated`
- campaign_target.send_status: `pending / sent / delivered / bounced / failed`
- track_event.event_type: `open / click / submit / report / attach_run / bounce`
- mail_report.classification: `pending / drill / real_phishing / false_positive / spam`
- ai_draft.status: `draft / approved / discarded`
- 风险等级: 0-30 低 / 31-70 中 / 71-100 高

## API 约定

- 前缀：`/api/v1/**`（管理端，JWT）、`/openapi/v1/**`（开放平台，OAuth2）、追踪/落地页走独立域名短路径（`/px/{token}.png`、`/t/{token}`、`/p/{slug}`、`/report/v1/**`）
- 统一响应：`{ code, message, data }`；分页 `{ page, pageSize, total, list }`
- 错误码分段：1xxx 通用 / 2xxx 认证权限 / 3xxx 参数 / 4xxx 业务 / 5xxx 集成 / 9xxx AI
- AI 流式：`POST /api/v1/ai/chat/stream`，SSE 帧 `{type: token|action|done|error}`
- 所有写操作写审计日志；所有列表接口强制数据权限过滤

## 安全与合规红线（不可妥协）

1. **口令类表单字段明文绝不落盘**——完整口令 AES-GCM 加密入库（密钥同敏感配置红线，取 证解密限管理端授权且全程审计）；日常展示只用"长度 + 首尾字符"（如 `X******6`）；≤2 位只存长度；解密取证 API 必须记录审计日志。
2. 敏感配置（SMTP 密码、API Key/Secret、DKIM 私钥、手机号）一律 AES-GCM 加密入库，API 只回显掩码。
3. 落地页/追踪服务必须与主平台**域名、IP 隔离**，禁止复用主平台域名。
4. 演练创建强制授权勾选（`auth_confirmed`），无授权不可启动。
5. ChatBI 生成的 SQL 必须经只读账号 + 表白名单 + 结构化校验 + 数据权限注入，禁止直接执行。
6. URL 克隆仅限客户自有系统页面，操作留审计；EXE/宏载荷功能默认关闭。
7. 数据留存期（`platform_setting.retention_days`）到期自动匿名化/删除。
8. 平台仅用于客户对自有员工的授权演练——不得提供可绕过该约束的"便利"实现。

## 开发约定

- 后端模块分包见《架构设计方案》§3.1（`app/modules/<模块>/{router,service,models,schemas}.py`）；新业务按模块归位，禁止跨模块大杂烩；模块间只经 service 层调用。
- I/O 密集路径（发信、DNS 检测、AI 调用、抓取）一律 async；通道适配器实现 `ChannelAdapter` Protocol。
- 参数校验用 Pydantic schema（schemas.py），router 只做绑定与响应包装，业务逻辑在 service 层。
- 数据库模型用 SQLAlchemy 2.0 Mapped 风格，结构变更必须生成 Alembic 迁移（`alembic revision --autogenerate`），禁止手改线上表。
- 实时计数写 Redis（`cnt:{campaignId}`），定时回写 `campaign_stat`；列表页读冗余表，报表读 `stat_daily` 汇总表。
- 追踪事件只进 Redis Stream（`evt:stream`），由消费者批量落库，禁止在 Track API 同步写 MySQL。
- 批次调度幂等（`uk_campaign_batch`）；事件去重按 token+event_type+时间窗；Celery 任务须可重试且幂等。
- 前端页面开发：先对照 `前端功能需求/` 对应 HTML 原型还原布局与字段，设计令牌（主色 #378ADD 等）在 `design-tokens.scss` 统一维护。
- AI 产出（模板/落地页/课程/报告摘要）一律走 `ai_draft` 草稿审核流，审核人/时间入审计。
- 报表与列表查询必须过数据权限过滤器（`core` 层封装），禁止裸查询。

## 模型路由约定

- 主对话固定 deepseek-v4-pro（会话内不随任务复杂度自动切换模型）
- 简单查找、单文件小改动、快速问答 → 优先派给 `quick` 子代理（haiku → deepseek-v4-flash，省 token）
- 多文件重构、架构级改动、深度审查、疑难 bug → `heavy` 子代理或主循环直接做（opus → deepseek-v4-pro）
- 派子代理时可按任务复杂度显式传 `model` 参数

## 分期范围（当前阶段判断依据）

- 一期 MVP：概览、演练管理(邮件)、用户和组、邮件模板+基础落地页、SMTP、基础报表、RBAC+审计
- 二期：培训、举报、EWS/SMS、克隆/二维码、部门/趋势报表、SIEM/Webhook、组织同步
- 三期：AI 全家桶、开放平台、旗舰授权、防识别增强
超出当前阶段的模块需求，先提示用户确认再动手。
