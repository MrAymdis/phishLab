/** API 模块索引：与后端 router 一一对应（后端路由为契约源）。 */
import { download, get, post, put, del } from './http'

// ---- 认证 / 个人中心 ----
export const authApi = {
  login: (username: string, password: string) =>
    post<{ token: string; account_id: number; username: string; real_name: string }>(
      '/api/v1/auth/login', { username, password },
    ),
  me: () => get<{ id: number; username: string; real_name: string }>('/api/v1/auth/me'),
  menus: () => get<{ path: string; title: string; icon: string }[]>('/api/v1/auth/menus'),
  updateProfile: (real_name: string) => put('/api/v1/auth/profile', { real_name }),
  changePassword: (old_password: string, new_password: string) =>
    put('/api/v1/auth/password', { old_password, new_password }),
}

// ---- 平台账号管理（RBAC 账号维度） ----
export const accountApi = {
  list: (q: { page?: number; pageSize?: number; kw?: string }) =>
    get<{ total: number; list: { id: number; username: string; real_name: string; status: number; last_login_at: string | null; created_at: string; roles: { id: number; name: string }[] }[] }>(
      '/api/v1/accounts', q as never,
    ),
  create: (payload: Record<string, unknown>) => post<{ id: number }>('/api/v1/accounts', payload),
  update: (id: number, payload: Record<string, unknown>) => put(`/api/v1/accounts/${id}`, payload),
  resetPassword: (id: number, new_password: string) =>
    put(`/api/v1/accounts/${id}/password`, { new_password }),
}

// ---- 数据概览 / 报表 ----
export const analyticsApi = {
  overview: (range: '7d' | 'month' | 'quarter') =>
    get('/api/v1/overview/metrics', { range }),
  campaignReport: (id: number) => get(`/api/v1/reports/campaign/${id}`),
  department: (range: string) => get('/api/v1/reports/department', { range }),
  deptPersons: (deptId: number, range: string) =>
    get(`/api/v1/reports/department/${deptId}/persons`, { range }),
  trend: (range: string) => get('/api/v1/reports/trend', { range }),
  personal: (uid: number) => get(`/api/v1/reports/personal/${uid}`),
  /** 导出报表文件（Excel/PDF，blob 下载） */
  exportReport: (payload: {
    kind: 'excel' | 'pdf'
    scope: 'campaign' | 'department' | 'trend' | 'personal'
    campaign_id?: number
    dept_id?: number
    user_id?: number
    range?: string
  }) => download('/api/v1/reports/export', payload),
}

// ---- 演练管理 ----
export interface CampaignQuery {
  status?: string
  type?: string
  kw?: string
  /** 时间范围（YYYY-MM-DD，服务端按演练起止时间过滤） */
  start_date?: string
  end_date?: string
  page?: number
  pageSize?: number
}
export const campaignApi = {
  list: (q: CampaignQuery) => get('/api/v1/campaigns', q as never),
  detail: (id: number) => get(`/api/v1/campaigns/${id}`),
  create: (payload: Record<string, unknown>) => post<{ id: number }>('/api/v1/campaigns', payload),
  saveDraft: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/campaigns/${id}/draft`, payload),
  start: (id: number) => post(`/api/v1/campaigns/${id}/start`),
  pause: (id: number) => post(`/api/v1/campaigns/${id}/pause`),
  resume: (id: number) => post(`/api/v1/campaigns/${id}/resume`),
  terminate: (id: number) => post(`/api/v1/campaigns/${id}/terminate`),
  deleteCampaign: (id: number) => del(`/api/v1/campaigns/${id}`),
  duplicateCampaign: (id: number) => post<{ id: number }>(`/api/v1/campaigns/${id}/duplicate`),
  dashboard: (id: number) => get(`/api/v1/campaigns/${id}/dashboard`),
  timeline: (id: number, page = 1) =>
    get(`/api/v1/campaigns/${id}/timeline`, { page, pageSize: 20 }),
  revealSubmitPassword: (id: number, eventId: number, body: { operation_password: string }) =>
    post<{ fields: { name: string; value: string }[]; event_id: number; user: string | null }>(
      `/api/v1/campaigns/${id}/events/${eventId}/reveal`, body,
    ),
  testSend: (id: number, to: string[]) => post(`/api/v1/campaigns/${id}/test-send`, to),
}

// ---- 用户和组 ----
export const orgApi = {
  deptTree: () => get('/api/v1/depts'),
  createDept: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/depts', payload),
  syncSource: (system: string) => post(`/api/v1/depts/sync?source=${system}`),
  overview: () =>
    get<{ total: number; dept_count: number; month_new: number; month_growth: number | null; high_risk: number; trained: number; training_pct: number }>(
      '/api/v1/emp-users/overview',
    ),
  users: (q: Record<string, unknown>) => get('/api/v1/emp-users', q),
  user: (id: number) => get(`/api/v1/emp-users/${id}`),
  createUser: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/emp-users', payload),
  updateUser: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/emp-users/${id}`, payload),
  deleteUser: (id: number) => del(`/api/v1/emp-users/${id}`),
  importUsersCsv: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post<{ imported: number; failed: number; errors: string[] }>(
      '/api/v1/emp-users/import', fd,
    )
  },
  riskProfile: (uid: number) => get(`/api/v1/emp-users/${uid}/risk-profile`),
  groups: () => get('/api/v1/groups'),
  tags: () => get('/api/v1/tags'),
  createTag: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/tags', payload),
}

// ---- 素材模板 ----
export const templateApi = {
  emailTemplates: (scene?: string) => get('/api/v1/email-templates', { scene } as never),
  getEmailTemplate: (id: number) => get(`/api/v1/email-templates/${id}`),
  createEmailTemplate: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/email-templates', payload),
  updateEmailTemplate: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/email-templates/${id}`, payload),
  duplicateEmailTemplate: (id: number) =>
    post<{ id: number }>(`/api/v1/email-templates/${id}/duplicate`),
  testSendEmailTemplate: (id: number, to: string[]) =>
    post(`/api/v1/email-templates/${id}/test-send`, to),
  landingPages: () => get('/api/v1/landing-pages'),
  getLandingPage: (id: number) => get(`/api/v1/landing-pages/${id}`),
  getLandingPagePreview: (id: number) => get(`/api/v1/landing-pages/${id}/preview`),
  createLandingPage: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/landing-pages', payload),
  updateLandingPage: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/landing-pages/${id}`, payload),
  duplicateLandingPage: (id: number) =>
    post<{ id: number }>(`/api/v1/landing-pages/${id}/duplicate`),
  cloneLandingPage: (url: string) => post<{ id: number }>('/api/v1/landing-pages/clone', { url }),
  payloads: () => get('/api/v1/attachments'),
  qrAssets: () => get('/api/v1/qr-assets'),
}

// ---- 发送配置 ----
export const channelApi = {
  list: () => get('/api/v1/channels'),
  overview: () =>
    get<{ monthly_sent: number; daily_avg: number }>('/api/v1/channels/overview'),
  createChannel: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/channels', payload),
  updateChannel: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/channels/${id}`, payload),
  deleteChannel: (id: number) => del(`/api/v1/channels/${id}`),
  test: (id: number, to?: string) =>
    post<{ ok: boolean; score: number; latency_ms: number | null; message: string }>(
      `/api/v1/channels/${id}/test?to=${to ?? ''}`,
    ),
  sendTestEmail: (id: number, to: string) =>
    post<{ ok: boolean; score: number; latency_ms: number | null; message: string }>(
      `/api/v1/channels/${id}/send-test`, { to },
    ),
  /** 演练向导预览发送：模板 + 落地页 + 伪装发件人的真实样式测试邮件 */
  sendTestEmailWithContent: (
    id: number,
    payload: { to: string; template_id?: number; landing_page_id?: number; sender_name?: string; domain?: string },
  ) =>
    post<{ ok: boolean; score: number; latency_ms: number | null; message: string }>(
      `/api/v1/channels/${id}/send-test-email`, payload,
    ),
  /** 用尚未保存的通道配置发测试邮件（不落库） */
  sendTestEmailDraft: (payload: Record<string, unknown>) =>
    post<{ ok: boolean; score: number; latency_ms: number | null; message: string }>(
      '/api/v1/channels/send-test', payload,
    ),
  senderProfiles: () => get('/api/v1/sender-profiles'),
  createSenderProfile: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/sender-profiles', payload),
  updateSenderProfile: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/sender-profiles/${id}`, payload),
  deleteSenderProfile: (id: number) => del(`/api/v1/sender-profiles/${id}`),
  testSenderProfile: (id: number, to: string) =>
    post<{ ok: boolean; score: number; latency_ms: number | null; message: string; note?: string }>(
      `/api/v1/sender-profiles/${id}/test-send`, { to },
    ),
  domains: () => get('/api/v1/domains'),
  createDomain: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/domains', payload),
  dnsCheck: (id: number) => get(`/api/v1/domains/${id}/dns-check`),
  deleteDomain: (id: number) => del(`/api/v1/domains/${id}`),
}

// ---- 培训 / 举报 ----
export const trainingApi = {
  // 课程
  courses: () => get('/api/v1/courses'),
  courseDetail: (id: number) => get(`/api/v1/courses/${id}`),
  createCourse: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/courses', payload),
  updateCourse: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/courses/${id}`, payload),
  /** 上传课程封面/课件（cover 图片 ≤2MB；content 文档音视频 ≤100MB），返回 /static 访问地址 */
  uploadCourseFile: (file: File, fileType: 'cover' | 'content') => {
    const fd = new FormData()
    fd.append('file', file)
    return post<{ url: string; size: number; filename: string }>(
      `/api/v1/courses/upload?file_type=${fileType}`, fd,
    )
  },
  deleteCourse: (id: number) => del(`/api/v1/courses/${id}`),
  // 培训任务
  tasks: () => get('/api/v1/training-tasks'),
  taskDetail: (id: number) => get(`/api/v1/training-tasks/${id}`),
  createTask: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/training-tasks', payload),
  closeTask: (id: number) => post(`/api/v1/training-tasks/${id}/close`),
  remindTask: (id: number) => post<{ undone: number }>(`/api/v1/training-tasks/${id}/remind`),
  deleteTask: (id: number) => del(`/api/v1/training-tasks/${id}`),
  exportTask: (id: number) => download(`/api/v1/training-tasks/${id}/export`),
  // 题库
  questionBank: () => get('/api/v1/exam/questions'),
  questionDetail: (id: number) => get(`/api/v1/exam/questions/${id}`),
  createQuestion: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/exam/questions', payload),
  updateQuestion: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/exam/questions/${id}`, payload),
  deleteQuestion: (id: number) => del(`/api/v1/exam/questions/${id}`),
  // 试卷
  papers: () => get('/api/v1/exam/papers'),
  paperDetail: (id: number) => get(`/api/v1/exam/papers/${id}`),
  createPaper: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/exam/papers', payload),
  updatePaper: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/exam/papers/${id}`, payload),
  publishPaper: (id: number, payload?: Record<string, unknown>) =>
    post<{ count: number; audience: Record<string, unknown> }>(`/api/v1/exam/papers/${id}/publish`, payload),
  deletePaper: (id: number) => del(`/api/v1/exam/papers/${id}`),
  // 考试记录
  examRecords: (q: Record<string, unknown>) => get('/api/v1/exam/records', q),
}
export const reportApi = {
  list: (q: Record<string, unknown>) => get('/api/v1/mail-reports', q),
  classify: (id: number, classification: string, remark?: string) =>
    post(`/api/v1/mail-reports/${id}/classify`, { classification, remark }),
  /** 举报中心统计卡 + 分类计数 */
  stats: () => get<{ total: number; monthCount: number; realCount: number; falseCount: number; drillCount: number; pendingCount: number; misreportRate: number }>('/api/v1/mail-reports/stats'),
  /** 积分排行榜（本月 + 累计 TOP20） */
  ranking: () => get<{ list: Record<string, unknown>[]; total: number }>('/api/v1/mail-reports/ranking'),
  /** 平台积分概览 + 最近兑换记录 */
  pointsOverview: () => get<{ totalIssued: number; monthIssued: number; participants: number; redemptions: Record<string, unknown>[] }>('/api/v1/mail-reports/points/overview'),
  /** 积分规则 */
  rewardRules: () => get<{ rules: { type: string; name: string; points: number; desc: string }[] }>('/api/v1/mail-reports/reward-rules'),
  updateRewardRules: (rules: Record<string, unknown>[]) =>
    put('/api/v1/mail-reports/reward-rules', { rules }),
  /** 兑换商品目录 / 员工兑换 */
  rewardCatalog: () => get<{ items: { id: number; name: string; icon: string; cost: number; stock: number }[] }>('/api/v1/mail-reports/reward-catalog'),
  redeem: (user_id: number, item_id: number) => post('/api/v1/mail-reports/redeem', { user_id, item_id }),
  /** 插件 API 配置 */
  pluginConfig: () => get<{ apiKeyMasked: string; allowedDomains: string[]; webhookUrl: string; autoclass: boolean; notifyChannels: Record<string, boolean> }>('/api/v1/mail-reports/plugin-config'),
  updatePluginConfig: (payload: Record<string, unknown>) =>
    put('/api/v1/mail-reports/plugin-config', payload),
  regenPluginKey: () => post<{ apiKeyMasked: string }>('/api/v1/mail-reports/plugin-config/regen-key'),
  testPluginWebhook: (webhookUrl: string) =>
    post<{ ok: boolean; status: number; message: string }>('/api/v1/mail-reports/plugin-config/test-webhook', { webhookUrl }),
}

// ---- AI ----
export const aiApi = {
  sessions: () => get('/api/v1/ai/sessions'),
  drafts: (status?: string) => get('/api/v1/ai/drafts', { status } as never),
  approveDraft: (id: number) => post(`/api/v1/ai/drafts/${id}/approve`),
  discardDraft: (id: number) => post(`/api/v1/ai/drafts/${id}/discard`),
  chatStream: (body: Record<string, unknown>) =>
    post<ReadableStream>('/api/v1/ai/chat/stream', body),
  generateTemplate: (params: Record<string, unknown>) =>
    post<{ draft_id: number }>('/api/v1/ai/templates/generate', params),
  analyzeReport: (kind: string, target: Record<string, unknown>) =>
    post<{ draft_id: number }>('/api/v1/ai/analysis/generate', { kind, target }),
}

// ---- OpenAPI ----
export const openapiApi = {
  apps: () => get('/api/v1/open-apps'),
  createApp: (payload: Record<string, unknown>) =>
    post<{ id: number; app_id: string; app_secret: string }>('/api/v1/open-apps', payload),
}

// ---- 系统设置 / 授权 ----
export const systemApi = {
  settings: () => get('/api/v1/settings'),
  /** 公开品牌信息（无鉴权：登录页名称/Logo/版权/备案） */
  publicSettings: () => get<{ name: string; logo: string; copyright: string; icp: string }>('/api/v1/settings/public'),
  updateSettings: (payload: Record<string, unknown>) => put('/api/v1/settings', payload),
  uploadLogo: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post<{ logo: string }>('/api/v1/settings/logo', fd)
  },
  license: () => get('/api/v1/license'),
  activateLicense: (code: string) => post('/api/v1/license/activate', { license_key: code }),
  importLicense: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post('/api/v1/license/offline-import', fd)
  },
  roles: () => get('/api/v1/roles'),
  rolePermissions: () => get('/api/v1/roles/permissions'),
  roleDetail: (id: number) => get(`/api/v1/roles/${id}`),
  createRole: (payload: Record<string, unknown>) => post<{ id: number }>('/api/v1/roles', payload),
  updateRole: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/roles/${id}`, payload),
  auditLogs: (q: Record<string, unknown>) => get('/api/v1/audit-logs', q),
  loginLogs: (q: Record<string, unknown>) => get('/api/v1/login-logs', q),
  webhooks: () => get('/api/v1/webhooks'),
  saveWebhook: (payload: Record<string, unknown>) => put('/api/v1/webhooks', payload),
  testWebhook: (payload: Record<string, unknown>) =>
    post<{ ok: boolean; status: number; message: string }>('/api/v1/webhooks/test', payload),
  siem: () => get('/api/v1/siem'),
}
