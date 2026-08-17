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

    <!-- 实时指标（dashboard 接口已接入；SSE /stream 实时刷新留待后续） -->
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

    <div class="card card-teal" style="margin: 12px 16px 16px">
      <div class="card-title">
        实时用户行为时间轴
        <el-tag size="small" effect="plain"><span class="live-dot" style="margin-right:4px" />实时更新</el-tag>
      </div>
      <BehaviorTimeline v-if="timeline.length" :events="timeline" />
      <el-empty v-else description="暂无行为数据（邮件投递后打开/点击将实时出现）" :image-size="48" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import FunnelChart from '@/components/business/FunnelChart.vue'
import BehaviorTimeline from '@/components/business/BehaviorTimeline.vue'
import type { TimelineEvent } from '@/components/business/BehaviorTimeline.vue'
import { campaignApi } from '@/api'

// dashboard/timeline 已接入接口；SSE 实时推送留待后续（TODO: SSE /stream）
const route = useRoute()
const campaignName = ref('Q3全员防钓鱼演练')
const campaignStatus = ref('running')

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const metrics = ref<{ label: string; value: string | number; sub?: string; accent: Accent }[]>([
  { label: '发送总数', value: '1,200', sub: '成功率 100%', accent: 'blue' },
  { label: '发送成功', value: '1,200', sub: '占比 100%', accent: 'purple' },
  { label: '已阅读', value: '856', sub: '阅读率 71.3%', accent: 'teal' },
  { label: '已点击', value: '324', sub: '点击率 27.0%', accent: 'orange' },
  { label: '中招人数', value: '187', sub: '中招率 15.6%', accent: 'red' },
  { label: '已举报', value: '268', sub: '举报率 22.3%', accent: 'green' },
])

const funnel = ref<{ name: string; value: number; rate?: string }[]>([
  { name: '发送总数', value: 1200, rate: '100%' },
  { name: '发送成功', value: 1200, rate: '100%' },
  { name: '已阅读', value: 856, rate: '71.3%' },
  { name: '已点击', value: 324, rate: '→37.8%' },
  { name: '输入数据', value: 187, rate: '→57.7%' },
  { name: '主动举报', value: 268, rate: '31.3%' },
])

const alerts = ref([
  { msg: '张某某（研发部）连续3次输入密码', time: '2 分钟前', advice: '建议下发专项培训' },
  { msg: '财务部整体中招率达到 32%', time: '15 分钟前', advice: '超阈值5个百分点' },
  { msg: '李某某（高管办）点击后10秒内提交', time: '38 分钟前', advice: '已自动推送培训' },
])

const timeline = ref<TimelineEvent[]>([
  { time: '2026-08-15 14:33:05', user: '王某某 · 市场部', action: '在登录页输入了密码', icon: '⚠️', ip: '10.12.34.56', browser: 'Chrome 125 · Win10', fingerprint: 'a3f8b2c1...', danger: true },
  { time: '2026-08-15 14:32:42', user: '王某某 · 市场部', action: '点击了邮件中的链接「立即报销」', icon: '🔗', ip: '10.12.34.56', browser: 'Chrome 125 · Win10' },
  { time: '2026-08-15 14:32:18', user: '王某某 · 市场部', action: '打开了邮件「财务报销通知」', icon: '📧', ip: '10.12.34.56', browser: 'Chrome 125 · Win10' },
  { time: '2026-08-15 14:31:55', user: '陈某某 · 法务部', action: '举报了可疑邮件', icon: '🛡️', ip: '10.12.78.90', browser: 'Edge 125 · macOS', good: true },
])

// ============ 接口数据加载（失败时保留演示数据） ============
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
  time: string
  user: string
  action: string
  icon: string
  ip: string
  browser: string
  fingerprint?: string | null
  danger?: boolean
  good?: boolean
}

async function load() {
  const id = Number(route.params.id)
  try {
    const [detail, dash, tl] = await Promise.all([
      campaignApi.detail(id),
      campaignApi.dashboard(id),
      campaignApi.timeline(id, 1),
    ])
    // 接口成功即覆盖（新演练为空数据 → 展示空状态而非演示数据）
    const dt = detail as CampaignDetailData | null
    campaignName.value = dt?.name || `演练 #${id}`
    campaignStatus.value = dt?.status || 'draft'

    const d = dash as CampaignDashData | null
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

    const list = (tl as { list?: TimelineDataItem[] } | null)?.list ?? []
    timeline.value = list.map((t) => ({
      time: t.time,
      user: t.user,
      action: t.action,
      icon: t.icon,
      ip: t.ip,
      browser: t.browser,
      fingerprint: t.fingerprint || undefined,
      danger: t.danger,
      good: t.good,
    }))
  } catch {
    // 仅在接口失败时保留演示数据
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
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

onMounted(load)
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
