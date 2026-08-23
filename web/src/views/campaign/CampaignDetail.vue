<template>
  <div class="page-container">
    <PageHeader :title="campaignName" :parents="['演练管理']">
      <template #actions>
        <StatusBadge :status="campaignStatus" />
        <el-button v-if="campaignStatus === 'running'" size="small" type="warning" :loading="actionLoading" @click="doPause">暂停</el-button>
        <el-button v-if="campaignStatus === 'paused'" size="small" type="primary" :loading="actionLoading" @click="doResume">恢复</el-button>
        <el-button v-if="['running', 'paused', 'scheduled', 'draft'].includes(campaignStatus)" size="small" type="danger" :loading="actionLoading" @click="doTerminate">终止</el-button>
      </template>
    </PageHeader>

    <!-- 实时指标（SSE /stream 推送；断线自动降级轮询） -->
    <el-row :gutter="12" style="margin: 16px 16px 0">
      <el-col :span="4" v-for="m in metrics" :key="m.label">
        <StatCard :title="m.label" :value="m.value" :sub="m.sub" :accent="m.accent" />
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin: 12px 16px 0">
      <el-col :span="10">
        <div class="card card-blue">
          <div class="card-title">转化漏斗</div>
          <FunnelChart :items="funnel" />
        </div>
      </el-col>
      <el-col :span="14">
        <div class="card card-red">
          <div class="card-title">
            高危中招预警
            <el-tag v-if="alerts.length" type="danger" size="small">{{ alerts.length }} 条</el-tag>
          </div>
          <div v-for="a in alerts" :key="a.msg" class="alert-row">
            <el-icon color="#A32D2D"><WarningFilled /></el-icon>
            <div>
              <div class="alert-msg">{{ a.msg }}</div>
              <div class="alert-meta">{{ a.time }} · {{ a.advice }}</div>
            </div>
          </div>
          <el-empty v-if="!alerts.length" description="暂无高危预警" :image-size="48" />
        </div>
      </el-col>
    </el-row>

    <!-- 投递失败列表（失败/退信邮箱 + 原因；随 SSE 刷新） -->
    <div v-if="deliveryFailures.length" class="card card-red" style="margin: 12px 16px 0">
      <div class="card-title">
        投递失败
        <el-tag type="danger" size="small">{{ deliveryFailures.length }} 条</el-tag>
      </div>
      <el-table :data="deliveryFailures" size="small" style="width: 100%">
        <el-table-column prop="name" label="员工" width="140" />
        <el-table-column prop="email" label="收件邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column prop="reason" label="失败原因" min-width="260" show-overflow-tooltip />
        <el-table-column prop="time" label="时间" width="160" />
      </el-table>
    </div>

    <div class="card card-teal" style="margin: 12px 16px 16px">
      <div class="card-title">
        实时用户行为时间轴
        <el-tag size="small" effect="plain"><span class="live-dot" style="margin-right:4px" />实时更新</el-tag>
      </div>
      <BehaviorTimeline v-if="timeline.length" :events="timeline" :campaign-id="Number(route.params.id)" />
      <el-empty v-else description="暂无行为数据（邮件投递后打开/点击将实时出现）" :image-size="48" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import FunnelChart from '@/components/business/FunnelChart.vue'
import BehaviorTimeline from '@/components/business/BehaviorTimeline.vue'
import type { TimelineEvent } from '@/components/business/BehaviorTimeline.vue'
import { campaignApi } from '@/api'
import { postSSE } from '@/composables/useSSE'
import { usePolling } from '@/composables/usePolling'

// dashboard/timeline/SSE 均已接入接口；SSE 断线时降级为轮询刷新
const route = useRoute()
const campaignName = ref('')
const campaignStatus = ref('draft')

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const metrics = ref<{ label: string; value: string | number; sub?: string; accent: Accent }[]>([])
const funnel = ref<{ name: string; value: number; rate?: string }[]>([])
const alerts = ref<{ msg: string; time: string; advice: string }[]>([])
const timeline = ref<TimelineEvent[]>([])
const deliveryFailures = ref<{ id: number; name: string; email: string; status: string; reason: string; time: string }[]>([])

// ============ 接口数据加载（失败保持空状态） ============
interface CampaignDetailData {
  id: number
  name: string
  type: string
  status: string
}
interface CampaignDashData {
  metrics: { label: string; value: string | number; suffix?: string; accent: string }[]
  funnel: { name: string; value: number; rate?: string | number }[]
  alerts: { msg: string; time: string; advice: string }[]
}
interface TimelineDataItem {
  id?: number
  time: string
  user: string
  action: string
  icon: string
  ip: string
  browser: string
  fingerprint?: string | null
  danger?: boolean
  good?: boolean
  detail?: Record<string, unknown> | null
}

function applyDash(d: CampaignDashData | null) {
  metrics.value = (d?.metrics ?? []).map((m) => ({
    label: m.label,
    value: m.value,
    sub: m.suffix ?? '',
    accent: m.accent as Accent,
  }))
  funnel.value = (d?.funnel ?? []).map((f) => ({
    name: f.name,
    value: f.value,
    rate: f.rate == null ? undefined : String(f.rate),
  }))
  alerts.value = (d?.alerts ?? []).map((a) => ({ msg: a.msg, time: a.time, advice: a.advice }))
}

function applyTimeline(list: TimelineDataItem[]) {
  timeline.value = list.map((t) => ({
    id: t.id,
    time: t.time,
    user: t.user,
    action: t.action,
    icon: t.icon,
    ip: t.ip,
    browser: t.browser,
    fingerprint: t.fingerprint || undefined,
    danger: t.danger,
    good: t.good,
    detail: t.detail || undefined,
  }))
}

async function load() {
  const id = Number(route.params.id)
  try {
    const [detail, dash, tl, df] = await Promise.all([
      campaignApi.detail(id),
      campaignApi.dashboard(id),
      campaignApi.timeline(id, 1),
      campaignApi.deliveryFailures(id, 1),
    ])
    // 接口成功即覆盖（新演练为空数据 → 展示空状态）
    const dt = detail as CampaignDetailData | null
    campaignName.value = dt?.name || `演练 #${id}`
    campaignStatus.value = dt?.status || 'draft'

    applyDash(dash as CampaignDashData | null)
    applyTimeline(((tl as { list?: TimelineDataItem[] } | null)?.list ?? []) as TimelineDataItem[])
    deliveryFailures.value = ((df as { list?: { id: number; name: string; email: string; status: string; reason: string; time: string }[] } | null)?.list ?? [])
  } catch {
    // 接口失败保持空状态，由 http 拦截器统一提示
  }
}

// ============ SSE 实时推送（快照直出 + 事件触发刷新；断线降级轮询） ============
type SseFrameData = { type: string; data?: Record<string, unknown> }
const sseConnected = ref(false)
let stopStream: (() => void) | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const polling = usePolling(() => load(), 5000)

/** SSE 断线 10 秒后自动重连（重连成功即停轮询；组件卸载时清理） */
function scheduleReconnect() {
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    startStream()
  }, 10000)
}

function startStream() {
  const id = Number(route.params.id)
  stopStream?.()
  polling.stop()
  sseConnected.value = false
  stopStream = postSSE({
    url: `/api/v1/campaigns/${id}/stream`,
    body: {},
    onFrame: (f) => {
      const frame = f as unknown as SseFrameData
      if (frame.type === 'snapshot') {
        // 连接成功：直接用快照渲染，避免与首屏请求重复
        sseConnected.value = true
        const snap = (frame.data ?? {}) as {
          dashboard?: CampaignDashData | null
          timeline?: TimelineDataItem[]
        }
        applyDash(snap.dashboard ?? null)
        applyTimeline(snap.timeline ?? [])
      } else if (frame.type === 'event' || frame.type === 'stats' || frame.type === 'alert') {
        void load() // 有增量：拉取最新指标/漏斗/预警/时间轴
      }
    },
    onError: () => {
      sseConnected.value = false
      polling.start()
      scheduleReconnect()
    },
    onClose: () => {
      sseConnected.value = false
      polling.start()
      scheduleReconnect()
    },
  })
}

const actionLoading = ref(false)

async function doPause() {
  const id = Number(route.params.id)
  actionLoading.value = true
  try {
    await campaignApi.pause(id)
    ElMessage.success('演练已暂停')
    await load()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    actionLoading.value = false
  }
}

async function doResume() {
  const id = Number(route.params.id)
  actionLoading.value = true
  try {
    await campaignApi.resume(id)
    ElMessage.success('演练已恢复')
    await load()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    actionLoading.value = false
  }
}

async function doTerminate() {
  const id = Number(route.params.id)
  actionLoading.value = true
  try {
    await campaignApi.terminate(id)
    ElMessage.success('演练已终止')
    await load()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  void load()
  startStream()
})
onUnmounted(() => {
  stopStream?.()
  polling.stop()
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
})
</script>

<style scoped lang="scss">
.alert-row {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border-bottom: none; }
}
.alert-msg {
  font-size: 13px;
}
.alert-meta {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
</style>
