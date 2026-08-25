# 开放平台 API（/openapi/v1）

客户系统对接网关：OAuth2 client_credentials 换取 access_token，按应用 scope 授权访问业务数据。所有调用落审计（`open_api_log`）。

## 鉴权流程

1. 平台管理端「API开放平台」创建应用 → 得到 `app_id` / `app_secret`（**仅创建时返回一次**）
2. 换取令牌：

```bash
curl -X POST https://<平台域名>/openapi/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type":"client_credentials","app_id":"app_xxx","app_secret":"sk_live_xxx"}'
# → {"access_token":"<JWT>","expires_in":7200,"scope":"campaign report"}
```

3. 业务调用携带 `Authorization: Bearer <access_token>`（有效期 2 小时）

## 网关约束（fail-closed）

| 校验 | 说明 |
|---|---|
| 应用状态 | 停用应用立即拒绝（403） |
| scope | token 与 DB 双侧校验——应用被收回权限后旧 token 立即失效 |
| IP 白名单 | 命中 `x-forwarded-for` 首个 IP（部署需 Nginx `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`） |
| 限流 | Redis 分钟计数，超过 `rate_limit` 返回 429（42902） |
| 审计 | 每次调用记录 method/path/状态码/延迟/IP/错误摘要（不记请求/响应正文） |

统一响应：`{code, message, data}`；HTTP 状态：401（令牌）、403（权限/白名单）、404、429（限流），参数错误为 200 + 业务 code。

## scope 与端点

| scope | 端点 | 说明 |
|---|---|---|
| **campaign** | `GET /campaigns` | 演练列表（分页 + status 过滤，含实时统计） |
| | `GET /campaigns/{cid}` | 演练详情（含中招统计） |
| | `POST /campaigns` | 创建演练草稿（见下方红线约束） |
| | `GET /campaigns/{cid}/targets` | 目标明细（`victim_only=true` 仅中招；中招 = 提交 + 附件运行） |
| | `GET /campaigns/{cid}/report` | 结果报表：指标卡 / 漏斗 / 中招明细 TOP20 / 近 14 天日趋势 |
| **report** | `GET /reports/overview` | 平台概览（演练/员工/部门/累计中招/举报） |
| | `GET /reports/trend?range=7d\|month\|quarter` | 中招趋势（按天） |
| | `GET /reports/department` | 部门中招对比（投递时间窗口，口径同内部报表） |
| **user** | `GET /users?kw=&dept_id=` | 员工列表（含行为统计） |
| | `GET /users/{uid}` | 员工详情（行为统计 + 最近 10 条行为事件） |
| **template** | `GET /templates?scene=` | 邮件模板列表（只读） |
| | `GET /templates/{tid}` | 模板详情（含正文） |
| **mail_report** | `GET /mail-reports?classification=` | 举报列表（只读） |
| **system** | `GET /system/info` | 平台基础信息 |

分页参数：`page` / `page_size`（≤100）。

## 红线约束（对接方须知）

- **创建演练**：`auth_confirmed` 必填 `true`（授权确认，红线 4），产物始终为**草稿**；启动发送仅在平台内人工操作，API 不提供启动/发送动作。
- **口令类数据**：中招明细仅返回提交行为标记，不返回任何口令内容（红线 1）。
- 数据可见性：应用 scope 授权即客户全量数据可见；部门级数据权限仅约束平台内部账号。

## 错误码

| code | 含义 | HTTP |
|---|---|---|
| 40101 / 40102 | 令牌缺失 / 已过期 | 401 |
| 40302 | 应用禁用 / scope 不足 / IP 不在白名单 | 403 |
| 10001 | 参数校验失败（如 auth_confirmed=false） | 200 |
| 10404 | 资源不存在 | 404 |
| 42902 | 超过限流阈值 | 429 |
