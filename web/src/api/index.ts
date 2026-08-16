/** API 模块索引：按后端模块一一对应（见《架构设计方案》§3.4）。 */
import { get, post, put, del } from './http'
import type {
  Campaign,
  OverviewMetrics,
  PageData,
  EmailTemplate,
  LandingPage,
  Payload,
  Channel,
  SenderIdentity,
  Domain,
  Dept,
  Employee,
  Group,
  Tag,
  Role,
  AuditLog,
  TrainingCourse,
  TrainingTask,
  ReportRow,
  AiDraft,
  OpenApiApp,
  ApiLog,
} from '@/types'

// ---- 认证 ----
export const authApi = {
  login: (username: string, password: string) =>
    post<{ token: string; account_id: number; username: string; real_name: string }>(
      '/api/v1/auth/login', { username, password },
    ),
  me: () => get<{ id: number; username: string; real_name: string }>('/api/v1/auth/me'),
  menus: () => get<unknown[]>('/api/v1/auth/menus'),
}

// ---- 数据概览 / 报表 ----
export const analyticsApi = {
  overview: (range: '7d' | 'month' | 'quarter') =>
    get<OverviewMetrics>('/api/v1/overview/metrics', { range }),
  campaignReport: (id: number) => get(`/api/v1/reports/campaign/${id}`),
  department: (range: string) => get('/api/v1/reports/department', { range }),
  trend: (range: string) => get('/api/v1/reports/trend', { range }),
  personal: (uid: number) => get(`/api/v1/reports/personal/${uid}`),
}

// ---- 演练管理 ----
export interface CampaignQuery {
  status?: string
  type?: string
  kw?: string
  page?: number
  pageSize?: number
}
export const campaignApi = {
  list: (q: CampaignQuery) => get<PageData<Campaign>>('/api/v1/campaigns', q as never),
  detail: (id: number) => get<Campaign>(`/api/v1/campaigns/${id}`),
  create: (payload: Record<string, unknown>) => post<{ id: number }>('/api/v1/campaigns', payload),
  saveDraft: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/campaigns/${id}/draft`, payload),
  start: (id: number) => post(`/api/v1/campaigns/${id}/start`),
  pause: (id: number) => post(`/api/v1/campaigns/${id}/pause`),
  resume: (id: number) => post(`/api/v1/campaigns/${id}/resume`),
  terminate: (id: number) => post(`/api/v1/campaigns/${id}/terminate`),
  dashboard: (id: number) => get(`/api/v1/campaigns/${id}/dashboard`),
  timeline: (id: number, page = 1) =>
    get(`/api/v1/campaigns/${id}/timeline`, { page, pageSize: 20 }),
  testSend: (id: number, to: string[]) => post(`/api/v1/campaigns/${id}/test-send`, to),
}

// ---- 用户和组 ----
export const orgApi = {
  deptTree: () => get<Dept[]>('/api/v1/depts'),
  users: (q: Record<string, unknown>) => get<PageData<Employee>>('/api/v1/emp-users', q),
  user: (id: number) => get<Employee>(`/api/v1/emp-users/${id}`),
  createUser: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/emp-users', payload),
  updateUser: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/emp-users/${id}`, payload),
  deleteUser: (id: number) => del(`/api/v1/emp-users/${id}`),
  importUsersCsv: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post<{ imported: number; failed: number }>('/api/v1/emp-users/import', fd)
  },
  exportUsersCsv: () => get<Blob>('/api/v1/emp-users/export'),
  riskProfile: (uid: number) => get(`/api/v1/emp-users/${uid}/risk-profile`),
  groups: () => get<Group[]>('/api/v1/groups'),
  createGroup: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/groups', payload),
  deleteGroup: (id: number) => del(`/api/v1/groups/${id}`),
  tags: () => get<Tag[]>('/api/v1/tags'),
  createTag: (payload: Record<string, unknown>) => post<{ id: number }>('/api/v1/tags', payload),
  deleteTag: (id: number) => del(`/api/v1/tags/${id}`),
  syncSource: (system: string) => post(`/api/v1/sync/${system}`),
}

// ---- 素材模板 ----
export const templateApi = {
  emailTemplates: (scene?: string) =>
    get<PageData<EmailTemplate>>('/api/v1/email-templates', { scene } as never),
  emailTemplate: (id: number) => get<EmailTemplate>(`/api/v1/email-templates/${id}`),
  createEmailTemplate: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/email-templates', payload),
  updateEmailTemplate: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/email-templates/${id}`, payload),
  deleteEmailTemplate: (id: number) => del(`/api/v1/email-templates/${id}`),
  testSendEmailTemplate: (id: number, to: string) =>
    post(`/api/v1/email-templates/${id}/test-send`, { to }),
  landingPages: () => get<PageData<LandingPage>>('/api/v1/landing-pages'),
  landingPage: (id: number) => get<LandingPage>(`/api/v1/landing-pages/${id}`),
  createLandingPage: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/landing-pages', payload),
  updateLandingPage: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/landing-pages/${id}`, payload),
  deleteLandingPage: (id: number) => del(`/api/v1/landing-pages/${id}`),
  cloneLandingPage: (url: string) => post<{ id: number }>('/api/v1/landing-pages/clone', { url }),
  payloads: () => get<Payload[]>('/api/v1/payloads'),
  createPayload: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/payloads', payload),
  deletePayload: (id: number) => del(`/api/v1/payloads/${id}`),
  generateQR: (content: string) => get<{ qr_url: string }>('/api/v1/tools/qrcode', { content }),
}

// ---- 发送配置 ----
export const channelApi = {
  list: () => get<Channel[]>('/api/v1/channels'),
  createChannel: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/channels', payload),
  updateChannel: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/channels/${id}`, payload),
  deleteChannel: (id: number) => del(`/api/v1/channels/${id}`),
  test: (id: number, to?: string) => post(`/api/v1/channels/${id}/test`, { to }),
  senderIdentities: () => get<SenderIdentity[]>('/api/v1/sender-identities'),
  createSenderIdentity: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/sender-identities', payload),
  deleteSenderIdentity: (id: number) => del(`/api/v1/sender-identities/${id}`),
  domains: () => get<Domain[]>('/api/v1/domains'),
  checkDomain: (id: number) => get(`/api/v1/domains/${id}/check`),
  dnsCheck: (id: number) => get(`/api/v1/domains/${id}/dns-check`),
}

// ---- 培训 / 举报 ----
export const trainingApi = {
  courses: () => get<TrainingCourse[]>('/api/v1/courses'),
  course: (id: number) => get<TrainingCourse>(`/api/v1/courses/${id}`),
  createCourse: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/courses', payload),
  questionBank: (course_id: number) => get(`/api/v1/courses/${course_id}/questions`),
  createQuestion: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/questions', payload),
  tasks: () => get<PageData<TrainingTask>>('/api/v1/training-tasks'),
  createTask: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/training-tasks', payload),
}
export const reportApi = {
  list: (q: Record<string, unknown>) => get<PageData<ReportRow>>('/api/v1/mail-reports', q),
  classify: (id: number, classification: string, remark?: string) =>
    post(`/api/v1/mail-reports/${id}/classify`, { classification, remark }),
  plugins: () => get('/api/v1/report/plugins'),
  rewardRanking: () => get('/api/v1/report/ranking'),
  handleReal: (id: number, remark: string) =>
    post(`/api/v1/mail-reports/${id}/handle-real`, { remark }),
}

// ---- AI ----
export const aiApi = {
  sessions: () => get('/api/v1/ai/sessions'),
  drafts: (status?: string) => get<PageData<AiDraft>>('/api/v1/ai/drafts', { status } as never),
  approveDraft: (id: number) => post(`/api/v1/ai/drafts/${id}/approve`),
  discardDraft: (id: number) => post(`/api/v1/ai/drafts/${id}/discard`),
  chatStream: (body: Record<string, unknown>) =>
    post<ReadableStream>('/api/v1/ai/chat/stream', body),
  generateTemplate: (params: Record<string, unknown>) =>
    post<{ id: number; name: string; subject: string; body: string }>(
      '/api/v1/ai/generate/template', params,
    ),
  analyzeReport: (type: string, id: number) =>
    get<{ summary: string; risk: string; suggestions: string[] }>(
      '/api/v1/ai/analyze/report', { type, id },
    ),
  models: () => get<{ id: string; name: string; provider: string }[]>('/api/v1/ai/models'),
  updateAiConfig: (payload: Record<string, unknown>) => put('/api/v1/ai/config', payload),
  usageStats: (range?: string) => get('/api/v1/ai/usage', { range }),
}

// ---- OpenAPI ----
export const openapiApi = {
  overview: () => get<{ app_count: number; call_count: number; error_count: number }>(
    '/api/v1/openapi/overview',
  ),
  apps: () => get<OpenApiApp[]>('/api/v1/openapi/apps'),
  createApp: (payload: Record<string, unknown>) =>
    post<{ id: number; app_id: string; app_secret: string }>('/api/v1/openapi/apps', payload),
  updateApp: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/openapi/apps/${id}`, payload),
  deleteApp: (id: number) => del(`/api/v1/openapi/apps/${id}`),
  regenerateSecret: (id: number) =>
    post<{ app_secret: string }>(`/api/v1/openapi/apps/${id}/regenerate-secret`),
  apiDocs: (category?: string) => get('/api/v1/openapi/docs', { category }),
  callLogs: (q: Record<string, unknown>) => get<PageData<ApiLog>>('/api/v1/openapi/logs', q),
}

// ---- 系统设置 / 授权 ----
export const systemApi = {
  settings: () => get('/api/v1/settings'),
  updateSettings: (payload: Record<string, unknown>) => put('/api/v1/settings', payload),
  license: () => get('/api/v1/license'),
  activateLicense: (code: string) => post('/api/v1/license/activate', { code }),
  importLicense: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post('/api/v1/license/import', fd)
  },
  roles: () => get<Role[]>('/api/v1/roles'),
  role: (id: number) => get<Role>(`/api/v1/roles/${id}`),
  createRole: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/roles', payload),
  updateRole: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/roles/${id}`, payload),
  deleteRole: (id: number) => del(`/api/v1/roles/${id}`),
  auditLogs: (q: Record<string, unknown>) => get<PageData<AuditLog>>('/api/v1/audit-logs', q),
  loginLogs: (q: Record<string, unknown>) => get<PageData<AuditLog>>('/api/v1/login-logs', q),
  ssoConfig: () => get('/api/v1/sso/config'),
  updateSso: (payload: Record<string, unknown>) => put('/api/v1/sso/config', payload),
  webhooks: () => get('/api/v1/webhooks'),
  updateWebhook: (payload: Record<string, unknown>) => put('/api/v1/webhooks', payload),
}
