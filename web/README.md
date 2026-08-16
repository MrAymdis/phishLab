# PhishLab Web（前端）

Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts。
视觉基准：`../前端功能需求/*.html` 静态原型；设计令牌在 `src/styles/design-tokens.scss`。

## 常用命令

```bash
npm install
npm run dev          # http://127.0.0.1:5173（/api 代理到后端 8080）
npm run build        # 产物 dist/（由 deploy/nginx.conf 托管）
npm run typecheck    # vue-tsc 类型检查
```

## 目录约定（见《架构设计方案》§2）

```
src/
├── api/          # http.ts(统一响应/40101跳登录) + index.ts(按后端模块分组)
├── components/
│   ├── base/     # StatCard / StatusBadge / BaseChart / PageHeader / ModulePlaceholder
│   ├── ai/       # AiCopilotDrawer(全局抽屉) / AiDraftCard(草稿审核)
│   └── business/ # FunnelChart / BehaviorTimeline
├── composables/  # useSSE(fetch+ReadableStream) / usePolling(降级轮询)
├── layouts/      # MainLayout(11项导航 + Copilot 挂载)
├── router/       # 路由 + 登录守卫
├── stores/       # user / permission / copilot / license
├── styles/       # design-tokens(继承 demo 视觉)
├── types/        # 与后端契约同步（ApiResult/Campaign/SseFrame）
└── views/        # 11 模块页面 + 登录 + 演练向导/详情
```

## 开发约定

- 页面开发先对照 `../前端功能需求/` 对应原型还原字段与布局；
- AI 回复走 SSE（`useSSE`），打字机渲染 Markdown；AI 产出统一经 `AiDraftCard` 草稿审核流；
- 后端未实现的接口返回 `code=10002`，前端 http 层已静默处理（不弹窗）；
- 列表页必须带分页参数（page/pageSize）；监控页优先 SSE、断线降级 `usePolling`。

## 测试账号

`admin / PhishLab@2026`（后端 `scripts/seed_admin.py` 生成）
