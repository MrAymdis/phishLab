# 举报插件：网页邮箱 EML 合成上报方案（二期设计稿）

> 状态：**已实施（2026-08-30，webmail 插件 v1.1.0）**——合成模块 `eml.js`、适配器框架 + Coremail 适配器 `adapters.js`、content/background 接线、服务端 `degrade` 备注已上线；Gmail/163/QQ 适配器仍待客户真实环境校准后补充。关联文档：`docs/举报插件部署说明.md`。
> 背景：EML 全文归档能力已上线（服务端解析/预览/下载/邮件头回填），但数据源目前只有 Outlook Web Add-in（`getAsFileAsync`）。Gmail / **Coremail** / 163 / QQ 等网页邮箱只能元数据上报，举报详情无正文、无附件、无邮件头。
> Coremail 是国内企业/高校/政府邮件的主流部署，是本方案的第一优先级适配对象。

## 1. 方案总览

网页邮箱扩展（MV3）在员工打开邮件的页面里**采集内容 → 在 JS 中合成一封 message/rfc822 → 走现有 `POST /report/v1/mail` 的 `eml_base64` 字段上传**。服务端零改动：解析、归档、预览、原件下载、邮件头回填全部复用现有链路。

```
员工打开邮件 → 点击悬浮「举报」按钮
  → content.js 按适配器选择器采集（头字段 / 正文 HTML / 附件链接）
  → 附件逐个 fetch（host_permissions 豁免 CORS，同源自带登录态）
  → 合成 MIME（multipart/mixed）
  → base64 → POST /report/v1/mail { eml_base64, ...元数据 }
  → 任一环节失败 → 分级降级（见 §5），上报不阻断
```

- EML 是**内容重建**，不要求与服务器原始报文字节一致；平台预览/下载/溯源基于内容，重建版完全够用。
- 合成全程在举报人自己的浏览器会话内完成，平台不需要服务账号、不需要厂商 API 开通，落地阻力最小。

## 2. 采集设计（适配器配置化）

厂商差异收敛到一份「选择器映射」。适配器 = 结构化选择器 + 后处理函数，按 URL/页面特征匹配。

```jsonc
// adapter 定义（配置化，二期可扩展更多厂商）
{
  "coremail": {
    "match": { "url": ["/coremail/"], "dom": { "hint": ".mailDetail" } },
    "fields": {
      "from":     ["css:.from-info .address", "css:.fl"],       // 选择器链，逐个尝试
      "to":       ["css:.to-info .address"],
      "cc":       ["css:.cc-info .address"],
      "subject":  ["css:.subject-title", "title"],
      "date":     ["css:.date-info"],
      "bodyHtml": ["css:.mail-content", "css:#content-frame"]
    },
    "attachments": {
      "list": ["css:.att-list .att-item"],
      "name": ["css:.att-name"],
      "url":  ["css:a[href]", "href"]     // 支持属性抽取
    }
  }
}
```

- 选择器链带兜底（改版小变动时第二个选择器仍能命中）；全部未命中 → 元数据模式（现状）。
- 采集仅在用户**点击举报的当前打开邮件**上执行，无任何后台扫描（红线 8：平台仅用于授权演练，插件不得越界读邮箱）。
- 正文取内容容器 `innerHTML`（保排版），摘录正文另取 `innerText` 供元数据降级展示。
- 附件 URL 形态：同源下载链接（最常见，自带登录态）；跨域 CDN/附件网关（`host_permissions: http(s)://*/*` 豁免 CORS，通常 token 在 URL 里）；`blob:` URL（页面创建，origin 范围内可 fetch）。三种都要支持。
- **Message-ID 说明**：页面 DOM 一般不暴露 RFC Message-ID（URL 里的 `mid=` 是 webmail 内部 ID，不能冒充）。合成 EML 不含 Message-ID，继续用元数据模式的发件人/主题人工研判；未来若某适配器能从「原文页」拿到真实 Message-ID 再启用（对应演练精确匹配、重复拦截）。

## 3. MIME 合成细节

手工拼 multipart（无第三方依赖，MV3 service worker 与 content script 均可用）：

```
From/To/Cc/Subject/Date           ← RFC 2047 encoded-word（显示名与主题的中文编码）
X-PhishLab-Source: webmail-synthesis
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="=phishlab.<随机串>"

--boundary
Content-Type: text/html; charset="utf-8"
Content-Transfer-Encoding: base64
<body HTML 的 base64>

--boundary
Content-Type: application/octet-stream
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename*=utf-8''<RFC 2231 百分号编码>
<附件字节 base64>
--boundary--
```

- 正文与附件一律 base64：规避 JS 字符串的编码陷阱（UTF-8 手动 `TextEncoder` 编码后再 b64）。
- 中文文件名用 RFC 2231 `filename*`，中文头字段用 RFC 2047（服务端 `policy.default` 解析无碍，下载后 Outlook 打开兼容）。
- 附件 mime 从下载响应 `Content-Type` 取，缺省 `application/octet-stream`。
- 附件抓取失败**只跳过该附件**，不拖垮整封（§5 分级）。

## 4. 服务端契约（已就绪，无改动）

- `POST /report/v1/mail`（X-Api-Key）新增使用现有字段 `eml_base64`。
- 解码上限 8MB（base64 约 10.7MB）——超限静默跳过归档，上报不阻断。维持不改；若二期有大量带附件邮件被拒，再评估上限与静态目录占用（红线 7 留存治理联动）。
- 邮件头回填：`headers` 缺失时从 EML 提取（现有逻辑）；合成 EML 的头字段与 payload 元数据保持一致（同一页面采集，天然一致）。

## 5. 降级策略（硬要求，逐级回落）

| 级别 | 触发条件 | 行为 |
|---|---|---|
| L1 完整 EML | 选择器命中 + 附件抓取成功 + 总大小 ≤ 8MB | 正文 + 全部附件 |
| L2 正文 EML | 附件全部/部分抓取失败，或总大小超限但正文可传 | 只含 text/html 部分 |
| L3 元数据 | 选择器未命中 / 正文也超限 / 合成异常 | 现状元数据上报（`eml_base64` 不带） |

任何异常不得阻断举报提交；降级原因（如 `attachments_skipped: 2`）随元数据可选上报，供管理员研判时知情。

## 6. 厂商适配器优先级

| 优先级 | 厂商 | 说明 |
|---|---|---|
| P0 | **Coremail** | 国内企业/高校/政府主流；界面多年稳定，适配成本低、覆盖广 |
| P1 | Gmail | DOM 混淆严重、附件走 token 化 CDN，成本高；有 Gmail Add-on（官方 API 取原文）作为替代路线 |
| P2 | 163 / QQ 邮箱 | 界面稳定，按需适配 |
| P3 | 自建/杂牌 webmail | 通用兜底选择器（语义化 `role`/`aria` 启发式），命中率低但无害 |

## 7. 安全与合规

- 仅采集用户当前打开的邮件（举报动作触发），无扫描、无遍历（红线 8）。
- 数据仅发往平台举报接口；EML 入库受 `platform_setting.retention_days` 留存治理（红线 7，现有机制）。
- 附件抓取不涉及服务端凭据；API Key 仍按现有 fail-closed 白名单与去重机制。
- 合成 EML 加 `X-PhishLab-Source` 头，与 Outlook 原件归档区分（取证场景可辨识为重建件）。

## 8. 二期实施计划

1. **MIME 合成模块**（纯函数，独立可测）：头编码 / boundary / 多 part 拼装 / UTF-8+b64。~1 天
2. **适配器框架**：选择器链求值 + 附件三态 URL 抓取 + 分级降级。~0.5 天
3. **Coremail 适配器**（P0）：需客户真实 webmail 环境校准选择器（设计阶段无法最终定稿）。~0.5 天
4. **测试**：合成模块单测（中文头/中文文件名/大小边界）；适配器用 fixture HTML 测；E2E 举报全链路。~1 天
5. 更新 `docs/举报插件部署说明.md` 与 admin 引导文案。~0.5 天

**验收标准**：
- Coremail 实测举报 → 详情预览有正文/附件清单/头字段；EML 下载后可用邮件客户端打开。
- 附件抓取失败 / 超 8MB / 改版选择器失效 → L2/L3 降级成功，无未捕获异常。
- 全量后端测试不回归（服务端无改动，回归即可）。

**风险**：网页邮箱改版破坏选择器（选择器链 + 降级兜底）；附件网关升级 token 机制（逐附件跳过）；大附件邮件普遍超 8MB（评估放宽上限，联动静态目录容量）。
