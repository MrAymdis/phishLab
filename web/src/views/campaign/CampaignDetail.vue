<template>
  <div class="page-container">
    <PageHeader title="Q3全员防钓鱼演练" :parents="['演练管理']">
      <template #actions>
        <StatusBadge status="running" />
        <el-button size="small" type="warning">暂停</el-button>
        <el-button size="small" type="danger">终止</el-button>
      </template>
    </PageHeader>

    <!-- 实时指标（TODO: GET /campaigns/{id}/dashboard + SSE /stream） -->
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
            <el-tag type="danger" size="small">3 条新</el-tag>
          </div>
          <div v-for="a in alerts" :key="a.msg" class="alert-row">
            <el-icon color="#A32D2D"><WarningFilled /></el-icon>
            <div>
              <div class="alert-msg">{{ a.msg }}</div>
              <div class="alert-meta">{{ a.time }} · {{ a.advice }}</div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="card card-teal" style="margin: 12px 16px 16px">
      <div class="card-title">
        实时用户行为时间轴
        <el-tag size="small" effect="plain"><span class="live-dot" style="margin-right:4px" />实时更新</el-tag>
      </div>
      <BehaviorTimeline :events="timeline" />
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import FunnelChart from '@/components/business/FunnelChart.vue'
import BehaviorTimeline from '@/components/business/BehaviorTimeline.vue'
import type { TimelineEvent } from '@/components/business/BehaviorTimeline.vue'

// TODO(一期)：campaignApi.dashboard(id) + SSE stream 实时刷新
type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const metrics: { label: string; value: string; sub: string; accent: Accent }[] = [
  { label: '发送总数', value: '1,200', sub: '成功率 100%', accent: 'blue' },
  { label: '发送成功', value: '1,200', sub: '占比 100%', accent: 'purple' },
  { label: '已阅读', value: '856', sub: '阅读率 71.3%', accent: 'teal' },
  { label: '已点击', value: '324', sub: '点击率 27.0%', accent: 'orange' },
  { label: '中招人数', value: '187', sub: '中招率 15.6%', accent: 'red' },
  { label: '已举报', value: '268', sub: '举报率 22.3%', accent: 'green' },
]

const funnel = [
  { name: '发送总数', value: 1200, rate: '100%' },
  { name: '发送成功', value: 1200, rate: '100%' },
  { name: '已阅读', value: 856, rate: '71.3%' },
  { name: '已点击', value: 324, rate: '→37.8%' },
  { name: '输入数据', value: 187, rate: '→57.7%' },
  { name: '主动举报', value: 268, rate: '31.3%' },
]

const alerts = [
  { msg: '张某某（研发部）连续3次输入密码', time: '2 分钟前', advice: '建议下发专项培训' },
  { msg: '财务部整体中招率达到 32%', time: '15 分钟前', advice: '超阈值5个百分点' },
  { msg: '李某某（高管办）点击后10秒内提交', time: '38 分钟前', advice: '已自动推送培训' },
]

const timeline: TimelineEvent[] = [
  { time: '2026-08-15 14:33:05', user: '王某某 · 市场部', action: '在登录页输入了密码', icon: '⚠️', ip: '10.12.34.56', browser: 'Chrome 125 · Win10', fingerprint: 'a3f8b2c1...', danger: true },
  { time: '2026-08-15 14:32:42', user: '王某某 · 市场部', action: '点击了邮件中的链接「立即报销」', icon: '🔗', ip: '10.12.34.56', browser: 'Chrome 125 · Win10' },
  { time: '2026-08-15 14:32:18', user: '王某某 · 市场部', action: '打开了邮件「财务报销通知」', icon: '📧', ip: '10.12.34.56', browser: 'Chrome 125 · Win10' },
  { time: '2026-08-15 14:31:55', user: '陈某某 · 法务部', action: '举报了可疑邮件', icon: '🛡️', ip: '10.12.78.90', browser: 'Edge 125 · macOS', good: true },
]
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
