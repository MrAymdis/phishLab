/** 与后端约定的通用类型（见《架构设计方案》§3.4）。 */

export interface ApiResult<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PageData<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

export type CampaignType = 'mail' | 'sms' | 'social' | 'usb'
export type CampaignStatus =
  | 'draft' | 'scheduled' | 'sending' | 'running'
  | 'paused' | 'completed' | 'terminated'

export interface Campaign {
  id: number
  name: string
  description?: string
  type: CampaignType
  status: CampaignStatus
  creator_id: number
  target_count: number
  schedule_type: 'now' | 'timed'
  schedule_at?: string
  batch_count: number
  training_policy: 'redirect' | 'popup' | 'none'
  started_at?: string
  ended_at?: string
  created_at: string
}

export interface OverviewMetrics {
  campaign_count: number
  target_count: number
  avg_submit_rate: number
  avg_report_rate: number
  training_pass_rate: number
  [key: string]: unknown
}

/** AI SSE 帧协议：{type: token|action|done|error} */
export interface SseFrame {
  type: 'token' | 'action' | 'done' | 'error'
  content?: string
  code?: number
  message?: string
  actions?: { label: string; route: string; params?: Record<string, unknown> }[]
}

export interface EmailTemplate {
  id: number
  name: string
  scene: string
  subject: string
  body: string
  built_in: boolean
  created_at: string
  used_count: number
}

export interface LandingPage {
  id: number
  name: string
  type: string
  category: string
  html_preview: string
  url: string
  created_at: string
}

export interface Payload {
  id: number
  name: string
  type: string
  desc: string
  size: number
  enabled: boolean
}

export type ChannelType = 'smtp' | 'ews' | 'sms'

export interface Channel {
  id: number
  name: string
  type: ChannelType
  config: Record<string, unknown>
  status: string
  delivery_score: number
  last_test?: string
}

export interface SenderIdentity {
  id: number
  name: string
  display_name: string
  address: string
  reply_to?: string
  scene_tags: string[]
  channel_id: number
}

export interface Domain {
  id: number
  domain: string
  spf_ok: boolean
  dkim_ok: boolean
  dmarc_ok: boolean
  score: number
  last_check?: string
}

export interface Dept {
  id: number
  name: string
  parent_id?: number
  child_count: number
  user_count: number
}

export interface Employee {
  id: number
  name: string
  email: string
  mobile?: string
  dept_id: number
  dept_name: string
  title?: string
  risk_score: number
  submit_count: number
  training_completion: number
  created_at: string
}

export interface Group {
  id: number
  name: string
  user_count: number
  created_at: string
}

export interface Tag {
  id: number
  name: string
  color: string
  user_count: number
}

export interface Role {
  id: number
  name: string
  description: string
  permissions: string[]
}

export interface AuditLog {
  id: number
  operator: string
  action: string
  target: string
  ip: string
  time: string
}

export interface TrainingCourse {
  id: number
  name: string
  type: string
  duration_min: number
  cover_url: string
  total_tasks: number
  completed_tasks: number
}

export interface TrainingTask {
  id: number
  course_name: string
  assignees: number
  deadline?: string
  status: string
  progress: number
}

export interface ReportRow {
  id: number
  subject: string
  sender: string
  reported_by: string
  reported_at: string
  classification: string
  is_real: boolean
  remark?: string
}

export interface AiDraft {
  id: number
  type: string
  title: string
  content_preview: string
  status: string
  created_at: string
  reviewer?: string
  reviewed_at?: string
}

export interface OpenApiApp {
  id: number
  app_id: string
  app_secret: string
  name: string
  description: string
  scopes: string[]
  rate_limit: number
  ip_whitelist: string[]
  call_count: number
  status: string
  created_at: string
}

export interface ApiLog {
  id: number
  time: string
  app_name: string
  method: string
  path: string
  status_code: number
  latency_ms: number
  ip: string
}
