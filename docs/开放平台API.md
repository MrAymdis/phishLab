# 开放平台 API（/openapi/v1）

客户系统对接网关：OAuth2 client_credentials 换取 access_token，按应用 scope 授权访问业务数据。所有调用落审计（`open_api_log`）。

## 接入流程

1. 平台管理端「API开放平台」→ 创建应用，勾选 scope → 得到 `app_id` / `app_secret`（**仅创建/重生成时返回一次明文**，其余只显示掩码）
2. 换取令牌：

```bash
curl -X POST https://<平台域名>/openapi/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type":"client_credentials","app_id":"app_xxx","app_secret":"sk_live_xxx"}'
# → {"code":0,"message":"ok","data":{"access_token":"<JWT>","expires_in":7200,"scope":"campaign report"}}
```

3. 业务调用携带 `Authorization: Bearer <access_token>`（有效期 **2 小时**，过期重新换取）

## 网关约束（fail-closed）

| 校验 | 说明 |
|---|---|
| 应用状态 | 停用应用立即拒绝（403），旧 token 同时失效 |
| scope | token 与 DB 双侧校验——应用被收回权限后旧 token 立即失效 |
| IP 白名单 | 命中 `x-forwarded-for` 首个 IP（部署需 Nginx `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`） |
| 限流 | Redis 分钟计数，超过应用 `rate_limit` 返回 429（42902） |
| 审计 | 每次调用记录 method/path/状态码/延迟/IP/错误摘要（不记请求/响应正文） |

统一响应：`{code, message, data}`；`code=0` 成功。错误码表见文末。

## 端点总览

| scope | 端点 | 说明 |
|---|---|---|
| —（无） | `POST /oauth/token` | 换取 access_token |
| **campaign** | `GET /campaigns` | 演练列表（分页 + status 过滤，含实时统计） |
| | `GET /campaigns/{cid}` | 演练详情（含中招统计） |
| | `POST /campaigns` | 创建演练草稿（红线约束见下） |
| | `GET /campaigns/{cid}/targets` | 目标明细（`victim_only=true` 仅中招） |
| | `GET /campaigns/{cid}/report` | 结果报表（指标卡/漏斗/中招明细 TOP20/近 14 天趋势） |
| **report** | `GET /reports/overview` | 平台概览指标 |
| | `GET /reports/trend?range=` | 中招趋势（按天） |
| | `GET /reports/department?range=` | 部门中招对比 |
| **user** | `GET /users?kw=&dept_id=` | 员工列表（含行为统计） |
| | `GET /users/{uid}` | 员工详情（行为统计 + 最近 10 条行为事件） |
| **template** | `GET /templates?scene=` | 邮件模板列表（只读，不含正文） |
| | `GET /templates/{tid}` | 模板详情（含正文） |
| **mail_report** | `GET /mail-reports?classification=` | 举报列表（只读） |
| **system** | `GET /system/info` | 平台基础信息 |

分页参数统一 `page`（默认 1）/ `page_size`（默认 20，≤100），返回 `{total, page, page_size, list}`。

**中招口径（全线一致）**：中招 = 提交表单 + 附件运行，与内部报表同一口径。

---

## 接口详情

### POST /oauth/token

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| grant_type | string | 是 | 固定 `client_credentials` |
| app_id | string | 是 | 应用 AppID（app_ 前缀） |
| app_secret | string | 是 | 应用 AppSecret（sk_live_ 前缀） |

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| access_token | string | JWT（HS256），2 小时有效 |
| expires_in | int | 有效期秒数（7200） |
| scope | string | 空格分隔的已授权 scope |

### GET /campaigns

Query：`status`（draft/scheduled/sending/running/paused/completed/terminated）、`page`、`page_size`。

响应 `data.list[]`：

| 字段 | 类型 | 说明 |
|---|---|---|
| id / name / type / status | int / string | 演练标识、类型（mail/sms/social/usb）、状态 |
| target_count | int | 目标人数 |
| schedule_type / schedule_at | string | 调度方式（now/timed）与定时时间 |
| started_at / ended_at / created_at | string | 起止/创建时间（`YYYY-MM-DD HH:MM:SS`） |
| stats | object | `{delivered, open, click, submit, attach, report}` 实时计数 |

### GET /campaigns/{cid}

在列表字段基础上追加：`description`、`batch_count`、`batch_interval_min`、`training_policy`、`victim_count`（中招数）、`victim_rate`（中招率 %）。

### POST /campaigns

请求体（节选关键字段，完整字段见管理端演练创建）：

```json
{
  "name": "Q3全员防钓鱼演练", "description": "模拟 HR 薪酬调整通知",
  "type": "mail", "template_id": 12, "landing_page_id": 3,
  "channel_id": 2, "sender_profile_id": 1,
  "target_mode": "dept", "target_snapshot": {"dept_ids": [5, 6]},
  "schedule_type": "timed", "schedule_at": "2026-09-01T09:00:00",
  "batch_count": 2, "batch_interval_min": 30, "time_jitter_sec": 60,
  "training_policy": "redirect", "training_redirect_url": "https://edu.example.com/security",
  "course_ids": [1],
  "auth_confirmed": true, "auth_snapshot": ["mail:authorized_internal_drill"]
}
```

响应：`data: {id}`（新演练 ID）。

> **红线约束**：`auth_confirmed` 必填 `true`（授权确认，红线 4）；产物始终为**草稿**（`schedule_type=now` → draft，`timed` → scheduled），API **不提供**启动/发送动作，发送仅在平台内人工操作。企微（social）演练 `auth_snapshot` 须含 `wecom:written_auth`/`wecom:domain_verified`/`wecom:internal_only`。

### GET /campaigns/{cid}/targets

Query：`victim_only`（bool，仅中招）、`page`、`page_size`。

响应 `data.list[]`：

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id / name / email / dept | — | 员工标识与部门 |
| send_status / sent_at | string | 投递状态（pending/sent/delivered/bounced/failed）与时间 |
| open_count / click_count | int | 打开/点击次数 |
| submit_flag / submit_at | bool / string | 是否提交表单及时间 |
| attach_run_count | int | 附件运行次数 |
| report_flag | bool | 是否举报 |
| victim | bool | 是否中招（提交或附件运行） |

### GET /campaigns/{cid}/report

响应 `data`：

| 字段 | 说明 |
|---|---|
| campaign | `{id, name, status}` |
| metrics | 指标卡数组：发送/打开/点击/中招/举报数（带 rate%）+ 综合得分 |
| funnel | 漏斗：发送→打开→点击→中招，逐级 count/rate（上级为 0 时 rate 为 null，不伪造 0%） |
| victims_top | 中招明细 TOP20：`{name, email, dept, submit, attach_run, click_count, open_count}` |
| daily | 近 14 天趋势：`{labels[], open[], click[], victim[]}` |

### GET /reports/overview

响应 `data`：`campaign_total`、`campaign_running`、`emp_total`、`dept_total`、`victim_total`、`report_total`、`last_campaign_at`。

### GET /reports/trend / GET /reports/department

Query：`range` = `7d` / `month` / `quarter`（默认 month）。

- trend → `{labels[], open[], click[], victim[]}`（按天）
- department → `{rows[]}`，每行：`dept, targetCount, victim, report, total, openRate, clickRate, submitRate, reportRate`（窗口内无投递时回退全量，与内部报表一致）

### GET /users

Query：`kw`（姓名/邮箱关键字）、`dept_id`、`page`、`page_size`。

响应 `data.list[]`：`id, emp_no, name, email, dept, position, status(active/inactive), behavior{campaigns, victim, open, click}`。

### GET /users/{uid}

列表字段 + `recent_events[]`：`{event_type(open/click/submit/attach_run), created_at}`（最近 10 条）。

### GET /templates / GET /templates/{tid}

- 列表：`id, name, scene, subject, source(builtin/custom/ai/cloned), status(draft/approved), stars, used_count, click_rate, created_at`
- 详情追加：`html_body, variables[], track_pixel, track_link, track_attach`

### GET /mail-reports

Query：`classification`（pending/drill/real_phishing/false_positive/spam）、`page`、`page_size`。

响应 `data.list[]`：`id, channel(outlook_plugin/webmail/manual/api), subject, from_addr, reporter_email, classification, classifier, matched_campaign_id, created_at, handled_at`。

### GET /system/info

响应 `data`：`app_name, campaign_total, emp_total, dept_total`。

---

## 错误码

| code | 含义 | HTTP |
|---|---|---|
| 0 | 成功 | 200 |
| 40101 | 缺少 Bearer access_token | 401 |
| 40102 | access_token 无效或已过期 | 401 |
| 40302 | 应用不存在/禁用、scope 不足或 IP 不在白名单 | 403 |
| 10404 | 资源不存在（ID 无效） | 404 |
| 42902 | 超过限流阈值 | 429 |
| 10001 | 参数校验失败（如 auth_confirmed 非 true） | 200 |

## 数据可见性

应用 scope 授权即客户全量数据可见（部门级数据权限仅约束平台内部账号）；中招明细仅返回行为标记，**不返回任何口令内容**（红线 1）。
