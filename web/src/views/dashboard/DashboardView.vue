<template>
  <div class="page-container">
    <PageHeader title="数据概览">
      <template #actions>
        <el-radio-group v-model="range" size="small">
          <el-radio-button value="7d">近7天</el-radio-button>
          <el-radio-button value="month">本月</el-radio-button>
          <el-radio-button value="quarter">本季度</el-radio-button>
        </el-radio-group>
      </template>
    </PageHeader>

    <!-- ChatBI 智能问数栏 -->
    <div class="chatbi-bar card card-purple" style="margin: 16px 16px 0">
      <div class="chatbi-head">
        <el-icon color="#7F77DD"><MagicStick /></el-icon>
        <span class="chatbi-title">ChatBI 智能问数</span>
        <span class="chatbi-sub">用自然语言查询演练数据，AI 自动生成只读 SQL 并可视化呈现</span>
      </div>
      <div class="chatbi-body">
        <el-input v-model="chatbiQuery" size="default" placeholder="例如：本月各部门中招率对比" clearable style="flex: 1" @keyup.enter="askChatBI">
          <template #append>
            <el-button type="primary" :icon="Promotion" :loading="chatbiLoading" @click="askChatBI">发送</el-button>
          </template>
        </el-input>
      </div>
      <el-dialog v-model="chatbiVisible" :title="chatbiResult?.title || '问数结果'" width="720px" append-to-body>
        <template v-if="chatbiResult">
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 8px"
            :title="`「${chatbiResult.question}」 共 ${chatbiResult.total} 行（只读查询，SQL 已留审计）`" />
          <el-table :data="chatbiRows" size="small" max-height="360" border>
            <el-table-column v-for="c in chatbiResult.columns" :key="c" :prop="c" :label="c" min-width="110" />
            <template #empty>无数据</template>
          </el-table>
          <el-collapse style="margin-top: 8px">
            <el-collapse-item title="查看执行 SQL" name="sql">
              <pre style="white-space: pre-wrap; word-break: break-all; font-size: 12px; color: #666">{{ chatbiResult.sql }}</pre>
            </el-collapse-item>
          </el-collapse>
        </template>
      </el-dialog>
      <div class="chatbi-suggest">
        <el-tag
          v-for="s in chatbiSuggestions"
          :key="s"
          size="small"
          effect="plain"
          class="chatbi-suggest-tag"
          @click="chatbiQuery = s; askChatBI()"
        >
          {{ s }}
        </el-tag>
      </div>
    </div>

    <!-- 核心指标（随筛选周期联动；真实数据 GET /api/v1/overview/metrics） -->
    <el-row :gutter="12" style="margin: 12px 16px 0">
      <el-col :span="4" v-for="m in coreMetrics" :key="m.title">
        <StatCard :title="m.title" :value="m.value" :suffix="m.suffix" :accent="m.accent" />
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin: 12px 16px 0">
      <el-col :span="8">
        <div class="card card-blue">
          <div class="card-title">演练活动方式分布</div>
          <BaseChart v-if="channelTotal > 0" :option="channelPie" height="240px" />
          <el-empty v-else description="暂无演练数据" :image-size="70" style="padding: 24px 0" />
        </div>
      </el-col>
      <el-col :span="16">
        <div class="card card-orange">
          <div class="card-title">风险趋势（中招人数 × 中招率）</div>
          <BaseChart :option="trendChart" height="240px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="equal-row" style="margin: 12px 16px 0">
      <el-col :span="8" class="equal-col">
        <div class="card card-red">
          <div class="card-title">
            <span>中招高危 TOP5 排行</span>
            <el-radio-group v-model="topDim" size="small">
              <el-radio-button value="person">人员</el-radio-button>
              <el-radio-button value="dept">部门</el-radio-button>
            </el-radio-group>
          </div>
          <template v-if="topDim === 'person'">
            <template v-if="topPersons.length">
              <div v-for="(p, idx) in topPersons" :key="p.name" class="rank-row">
                <span class="rank-no" :style="{ color: rankColors[idx] }">{{ idx + 1 }}</span>
                <span class="rank-pname">{{ p.name }}</span>
                <span class="rank-dept">{{ p.dept }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: p.bar + '%', background: rankColors[idx] }" />
                </div>
                <span class="rank-count">{{ p.count }}</span>
              </div>
            </template>
            <el-empty v-else description="暂无中招人员数据" :image-size="60" style="padding: 12px 0" />
          </template>
          <template v-else>
            <template v-if="topDepts.length">
              <div v-for="(d, idx) in topDepts" :key="d.name" class="rank-row">
                <span class="rank-no" :style="{ color: rankColors[idx] }">{{ idx + 1 }}</span>
                <span class="rank-pname">{{ d.name }}</span>
                <span class="rank-dept">&nbsp;</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: d.bar + '%', background: rankColors[idx] }" />
                </div>
                <span class="rank-count">{{ d.count }}</span>
              </div>
            </template>
            <el-empty v-else description="暂无部门数据" :image-size="60" style="padding: 12px 0" />
          </template>
        </div>
      </el-col>
      <el-col :span="8" class="equal-col">
        <div class="card card-purple">
          <div class="card-title">浏览器指纹分布</div>
          <BaseChart v-if="fingerprintTotal > 0" :option="fingerprintPie" height="220px" />
          <el-empty v-else description="暂无指纹数据" :image-size="70" style="padding: 24px 0" />
        </div>
      </el-col>
      <el-col :span="8" class="equal-col">
        <div class="card card-teal">
          <div class="card-title">素材模板运营数据</div>
          <div class="ops-grid">
            <div v-for="(o, i) in opsData" :key="o.label" class="ops-item" :class="{ 'ops-span2': i === opsData.length - 1 }">
              <div class="ops-label">{{ o.label }}</div>
              <div class="ops-value">{{ o.value }}</div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="equal-row" style="margin: 12px 16px 16px">
      <el-col :span="12" class="equal-col">
        <div class="card card-green">
          <div class="card-title">
            <span><span class="live-dot" /> 进行中的演练{{ liveCampaignName ? ` · ${liveCampaignName}` : ' · 暂无' }}</span>
            <span v-if="liveCampaignName" class="live-realtime"><span class="live-dot" /> 实时</span>
          </div>
          <div class="live-bar-list">
            <div v-for="s in liveStats" :key="s.label" class="live-bar-row">
              <span class="live-bar-label">{{ s.label }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: s.bar + '%', background: s.color }" />
              </div>
              <span class="live-bar-value">{{ s.value }}</span>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :span="12" class="equal-col">
        <div class="card card-blue">
          <div class="card-title">
            <span>近期计划演练</span>
            <span class="plan-link">查看全部</span>
          </div>
          <table class="plan-table">
            <thead>
              <tr>
                <th>活动名称</th>
                <th>日期</th>
                <th>类型</th>
                <th>目标</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!plans.length">
                <td colspan="5" style="text-align: center; color: var(--color-text-tertiary); padding: 16px 0">暂无计划演练</td>
              </tr>
              <tr v-for="p in plans" :key="p.name">
                <td class="plan-t-name">{{ p.name }}</td>
                <td>{{ p.date }}</td>
                <td>{{ p.type }}</td>
                <td>{{ p.target }}</td>
                <td class="plan-t-status">
                  <span class="plan-badge" :class="p.status === '筹备中' ? 'badge-warning' : 'badge-info'">{{ p.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import { MagicStick, Promotion } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import BaseChart from '@/components/base/BaseChart.vue'
import { aiApi, analyticsApi, type ChatbiResult } from '@/api'

const range = ref<'7d' | 'month' | 'quarter'>('month')

// ============ ChatBI 智能问数 ============
const chatbiQuery = ref('')
const chatbiLoading = ref(false)
const chatbiVisible = ref(false)
const chatbiResult = shallowRef<ChatbiResult | null>(null)
const chatbiSuggestions = [
  '本月各部门中招率对比',
  '近7天举报趋势',
  '高风险人员名单',
  '培训通过率最低的部门',
]

/** 行数据转对象数组（动态列渲染 el-table） */
const chatbiRows = computed(() => {
  const r = chatbiResult.value
  if (!r) return []
  return r.rows.map((row) => {
    const obj: Record<string, unknown> = {}
    r.columns.forEach((c, i) => { obj[c] = row[i] })
    return obj
  })
})

async function askChatBI() {
  const q = chatbiQuery.value.trim()
  if (!q || chatbiLoading.value) return
  chatbiLoading.value = true
  try {
    // 只读账号 + 表白名单 + 数据权限注入 + 审计（红线 5，后端已强制）
    chatbiResult.value = await aiApi.chatbi(q)
    chatbiVisible.value = true
  } catch {
    /* 错误已由 http 层提示 */
  } finally {
    chatbiLoading.value = false
  }
}

// ============ 数据区（全部来自 GET /api/v1/overview/metrics，无 mock） ============
const topDim = ref<'person' | 'dept'>('person')
const rankColors = ['#A32D2D', '#D85A30', '#D85A30', '#EF9F27', '#EF9F27']
const topPersons = ref<{ name: string; dept: string; count: string | number; bar: number }[]>([])
const topDepts = ref<{ name: string; count: string | number; bar: number }[]>([])

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const coreMetrics = ref<{ title: string; value: string | number; suffix: string; accent: Accent }[]>([])

const channelPie = shallowRef<EChartsOption>({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: { fontSize: 11 } },
  series: [{ type: 'pie', radius: ['38%', '62%'], label: { fontSize: 11 }, data: [] }],
})

const trendChart = shallowRef<EChartsOption>({
  tooltip: { trigger: 'axis' },
  legend: { data: ['中招人数', '中招率%'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 40, top: 34, bottom: 24 },
  xAxis: { type: 'category', data: [] },
  yAxis: [
    { type: 'value', name: '人数' },
    { type: 'value', name: '%', max: 40 },
  ],
  series: [
    { name: '中招人数', type: 'bar', barWidth: 22, data: [], itemStyle: { color: '#378ADD' } },
    { name: '中招率%', type: 'line', yAxisIndex: 1, data: [], itemStyle: { color: '#D85A30' } },
  ],
})

const fingerprintPie = shallowRef<EChartsOption>({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: { fontSize: 11 } },
  series: [{ type: 'pie', radius: '58%', label: { fontSize: 11 }, data: [] }],
})

const liveStats = ref<{ label: string; value: string | number; bar: number; color: string }[]>([])
const liveCampaignName = ref('')
const opsData = ref<{ label: string; value: string | number }[]>([])
const plans = ref<{ name: string; date: string; type: string; target: string; status: string }[]>([])

const channelTotal = computed(() => {
  const s = channelPie.value.series as { data: { value: number }[] }[]
  return s[0]?.data?.reduce((sum, i) => sum + (i.value || 0), 0) ?? 0
})
const fingerprintTotal = computed(() => {
  const s = fingerprintPie.value.series as { data: { value: number }[] }[]
  return s[0]?.data?.reduce((sum, i) => sum + (i.value || 0), 0) ?? 0
})

// ============ 接口数据加载 ============
interface OverviewData {
  coreMetrics: { title: string; value: string | number; suffix: string; accent: Accent }[]
  topPersons: { name: string; dept: string; count: string | number; bar: number }[]
  topDepts: { name: string; count: string | number; bar: number }[]
  liveStats: { label: string; value: string | number; bar: number; color: string }[]
  liveCampaignName?: string
  opsData: { label: string; value: string | number }[]
  plans: { name: string; date: string; type: string; target: string; status: string }[]
  channelDist: { name: string; value: number }[]
  trend: { labels: string[]; victims: number[]; victimRates: number[] }
  fingerprints: { name: string; value: number }[]
}

async function load() {
  try {
    const d = (await analyticsApi.overview(range.value)) as OverviewData | null
    if (!d) return
    coreMetrics.value = d.coreMetrics ?? []
    topPersons.value = d.topPersons ?? []
    topDepts.value = d.topDepts ?? []
    liveStats.value = d.liveStats ?? []
    liveCampaignName.value = d.liveCampaignName ?? ''
    opsData.value = d.opsData ?? []
    plans.value = d.plans ?? []
    // 图表数据：shallowRef 需整体替换以触发更新
    if (d.channelDist) {
      const series = channelPie.value.series as { data: { name: string; value: number }[] }[]
      channelPie.value = {
        ...channelPie.value,
        series: [{ ...series[0], data: d.channelDist }],
      } as EChartsOption
    }
    if (d.fingerprints) {
      const series = fingerprintPie.value.series as { data: { name: string; value: number }[] }[]
      fingerprintPie.value = {
        ...fingerprintPie.value,
        series: [{ ...series[0], data: d.fingerprints }],
      } as EChartsOption
    }
    if (d.trend) {
      const series = trendChart.value.series as { data: number[] }[]
      trendChart.value = {
        ...trendChart.value,
        xAxis: { ...(trendChart.value.xAxis as { data: string[] }), data: d.trend.labels ?? [] },
        series: [
          { ...series[0], data: d.trend.victims ?? [] },
          { ...series[1], data: d.trend.victimRates ?? [] },
        ],
      } as EChartsOption
    }
  } catch {
    ElMessage.warning('接口数据加载失败，请检查网络或后端服务')
  }
}

onMounted(load)
watch(range, load)
</script>

<style scoped lang="scss">
.equal-col {
  display: flex;
}
.equal-col > .card {
  width: 100%;
}
.chatbi-bar {
  padding: 14px 16px;
}
.chatbi-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.chatbi-title {
  font-size: 14px;
  font-weight: 600;
}
.chatbi-sub {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
.chatbi-body {
  display: flex;
}
.chatbi-suggest {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.chatbi-suggest-tag {
  cursor: pointer;
  &:hover {
    color: var(--color-text-info);
    border-color: var(--color-border-info);
  }
}
.rank-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.rank-no {
  font-size: 12px;
  font-weight: 500;
  width: 18px;
  flex-shrink: 0;
}
.rank-pname {
  font-size: 12px;
  color: var(--color-text-primary);
  width: 48px;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-dept {
  font-size: 11px;
  color: var(--color-text-secondary);
  width: 50px;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  width: 32px;
  text-align: right;
  flex-shrink: 0;
}
.bar-track {
  background: var(--color-background-tertiary);
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
  flex: 1;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}
.live-realtime {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-success);
  font-weight: 400;
}
.live-bar-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.live-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.live-bar-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  width: 48px;
  flex-shrink: 0;
}
.live-bar-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  width: 44px;
  text-align: right;
  flex-shrink: 0;
}
.plan-link {
  font-size: 11px;
  color: var(--color-text-info);
  font-weight: 400;
  cursor: pointer;
}
.plan-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  table-layout: fixed;
  th {
    text-align: left;
    padding: 8px 0;
    font-weight: 500;
    color: var(--color-text-secondary);
    font-size: 11px;
    border-bottom: 0.5px solid var(--color-border-tertiary);
  }
  td {
    padding: 8px 0;
    color: var(--color-text-secondary);
    border-bottom: 0.5px solid var(--color-border-tertiary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  tr:last-child td {
    border-bottom: none;
  }
}
.plan-t-name {
  color: var(--color-text-primary) !important;
}
.plan-t-status {
  text-align: right;
}
.plan-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.badge-info {
  background: var(--color-background-info);
  color: var(--color-text-info);
}
.badge-warning {
  background: var(--color-background-warning);
  color: var(--color-text-warning);
}
.ops-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.ops-item {
  padding: 8px 10px;
  background: var(--color-background-secondary);
  border-radius: 8px;
}
.ops-span2 {
  grid-column: span 2;
}
.ops-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}
.ops-value {
  font-size: 18px;
  font-weight: 500;
  color: var(--color-text-primary);
}
</style>
