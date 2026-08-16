/** API 模块索引：与后端 router 一一对应（后端路由为契约源）。 */
import { get, post, put, del } from './http'

// ---- 认证 ----
export const authApi = {
  login: (username: string, password: string) =>
    post<{ token: string; account_id: number; username: string; real_name: string }>(
      '/api/v1/auth/login', { username, password },
    ),
  me: () => get<{ id: number; username: string; real_name: string }>('/api/v1/auth/me'),
  menus: () => get<{ path: string; title: string; icon: string }[]>('/api/v1/auth/menus'),
}

// ---- 数据概览 / 报表 ----
export const analyticsApi = {
  overview: (range: '7d' | 'month' | 'quarter') =>
    get('/api/v1/overview/metrics', { range }),
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
  list: (q: CampaignQuery) => get('/api/v1/campaigns', q as never),
  detail: (id: number) => get(`/api/v1/campaigns/${id}`),
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
  deptTree: () => get('/api/v1/depts'),
  createDept: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/depts', payload),
  syncSource: (system: string) => post(`/api/v1/depts/sync?source=${system}`),
  users: (q: Record<string, unknown>) => get('/api/v1/emp-users', q),
  user: (id: number) => get(`/api/v1/emp-users/${id}`),
  createUser: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/emp-users', payload),
  updateUser: (id: number, payload: Record<string, unknown>) =>
    put(`/api/v1/emp-users/${id}`, payload),
  deleteUser: (id: number) => del(`/api/v1/emp-users/${id}`),
  riskProfile: (uid: number) => get(`/api/v1/emp-users/${uid}/risk-profile`),
  groups: () => get('/api/v1/groups'),
  tags: () => get('/api/v1/tags'),
}

// ---- 素材模板 ----
export const templateApi = {
  emailTemplates: (scene?: string) => get('/api/v1/email-templates', { scene } as never),
  createEmailTemplate: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/email-templates', payload),
  testSendEmailTemplate: (id: number, to: string[]) =>
    post(`/api/v1/email-templates/${id}/test-send`, to),
  landingPages: () => get('/api/v1/landing-pages'),
  createLandingPage: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/landing-pages', payload),
  cloneLandingPage: (url: string) => post<{ id: number }>('/api/v1/landing-pages/clone', { url }),
  payloads: () => get('/api/v1/attachments'),
  qrAssets: () => get('/api/v1/qr-assets'),
}

// ---- 发送配置 ----
export const channelApi = {
  list: () => get('/api/v1/channels'),
  createChannel: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/channels', payload),
  test: (id: number, to?: string) => post(`/api/v1/channels/${id}/test?to=${to ?? ''}`),
  senderProfiles: () => get('/api/v1/sender-profiles'),
  createSenderProfile: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/sender-profiles', payload),
  domains: () => get('/api/v1/domains'),
  createDomain: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/domains', payload),
  dnsCheck: (id: number) => get(`/api/v1/domains/${id}/dns-check`),
}

// ---- 培训 / 举报 ----
export const trainingApi = {
  courses: () => get('/api/v1/courses'),
  createCourse: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/courses', payload),
  tasks: () => get('/api/v1/training-tasks'),
  createTask: (payload: Record<string, unknown>) =>
    post<{ id: number }>('/api/v1/training-tasks', payload),
  questionBank: () => get('/api/v1/exam/questions'),
  papers: () => get('/api/v1/exam/papers'),
}
export const reportApi = {
  list: (q: Record<string, unknown>) => get('/api/v1/mail-reports', q),
  classify: (id: number, classification: string, remark?: string) =>
    post(`/api/v1/mail-reports/${id}/classify`, { classification, remark }),
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
  updateSettings: (payload: Record<string, unknown>) => put('/api/v1/settings', payload),
  license: () => get('/api/v1/license'),
  activateLicense: (code: string) => post('/api/v1/license/activate', { license_key: code }),
  importLicense: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post('/api/v1/license/offline-import', fd)
  },
  roles: () => get('/api/v1/roles'),
  auditLogs: (q: Record<string, unknown>) => get('/api/v1/audit-logs', q),
  loginLogs: (q: Record<string, unknown>) => get('/api/v1/login-logs', q),
  webhooks: () => get('/api/v1/webhooks'),
  siem: () => get('/api/v1/siem'),
}
