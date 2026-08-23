<template>
  <div class="page-container">
    <PageHeader title="演练管理">
      <template #actions>
        <el-button :icon="Download" @click="batchExport">批量导出</el-button>
        <el-button type="primary" :icon="Plus" @click="$router.push('/campaign/create')">
          发起演练
        </el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片筛选 -->
    <el-row :gutter="12" style="margin: 16px 16px 0">
      <el-col :span="4" v-for="c in statCards" :key="c.label">
        <div class="card stat-mini" :class="`card-${c.accent}`" :style="{ cursor: 'pointer' }"
             @click="statusFilter = c.key">
          <div class="stat-title">{{ c.label }}</div>
          <div class="stat-value">{{ c.value }}</div>
          <div class="stat-sub">{{ c.sub }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="card" style="margin: 12px 16px">
      <div class="toolbar">
        <el-radio-group v-model="statusFilter" size="small">
          <el-radio-button value="">全部<span class="filter-count">{{ statusCounts.all }}</span></el-radio-button>
          <el-radio-button value="sending">发送中<span class="filter-count">{{ statusCounts.sending }}</span></el-radio-button>
          <el-radio-button value="running">进行中<span class="filter-count">{{ statusCounts.running }}</span></el-radio-button>
          <el-radio-button value="scheduled">待开始<span class="filter-count">{{ statusCounts.scheduled }}</span></el-radio-button>
          <el-radio-button value="completed">已完成<span class="filter-count">{{ statusCounts.completed }}</span></el-radio-button>
          <el-radio-button value="terminated">已终止<span class="filter-count">{{ statusCounts.terminated }}</span></el-radio-button>
        </el-radio-group>
        <el-select v-model="typeFilter" size="small" placeholder="全部类型" clearable style="width: 140px">
          <el-option label="邮件钓鱼" value="mail" />
          <el-option label="短信钓鱼" value="sms" />
          <el-option label="社交媒体钓鱼" value="social" />
          <el-option label="USB实物钓鱼" value="usb" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          size="small"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 240px"
        />
        <el-input v-model="kw" size="small" placeholder="搜索演练名称" style="width: 200px" clearable />
      </div>

      <el-table :data="pagedRows" size="small" style="margin-top: 12px" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="42" />
        <el-table-column label="演练名称" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/campaign/${row.id}`)">
              {{ row.name }}
            </el-link>
            <div class="name-sub">{{ statusSubText(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ TYPE_LABEL[row.type] }}</template>
        </el-table-column>
        <el-table-column label="时间范围" width="190" prop="time_range" />
        <el-table-column label="目标规模" width="90" align="right">
          <template #default="{ row }">{{ row.target_count.toLocaleString() }} 人</template>
        </el-table-column>
        <el-table-column label="进度（投递 → 阅读 → 点击 → 中招）" min-width="240">
          <template #default="{ row }">
            <div class="stage-progress">
              <div class="stage-row">
                <span class="stage-label">投递</span>
                <el-progress :percentage="row.deliver_rate" :stroke-width="5" color="#378ADD" :show-text="false" style="flex: 1" />
                <span class="stage-val">{{ row.deliver_rate }}%</span>
              </div>
              <div class="stage-row">
                <span class="stage-label">阅读</span>
                <el-progress :percentage="row.open_rate" :stroke-width="5" color="#13C2C2" :show-text="false" style="flex: 1" />
                <span class="stage-val">{{ row.open_rate }}%</span>
              </div>
              <div class="stage-row">
                <span class="stage-label">点击</span>
                <el-progress :percentage="row.click_rate" :stroke-width="5" color="#FAAD14" :show-text="false" style="flex: 1" />
                <span class="stage-val">{{ row.click_rate }}%</span>
              </div>
              <div class="stage-row">
                <span class="stage-label">中招</span>
                <el-progress :percentage="row.victim_rate" :stroke-width="5" color="#A32D2D" :show-text="false" style="flex: 1" />
                <span class="stage-val">{{ row.victim_rate }}%</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><StatusBadge :status="row.status" /></template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'draft' || row.status === 'scheduled'" link type="primary" size="small" @click="doEdit(row)">编辑</el-button>
                <el-button v-if="row.status === 'draft' || row.status === 'scheduled'" link type="primary" size="small" @click="doStart(row)">启动</el-button>
                <el-button v-if="row.status === 'draft' || row.status === 'scheduled'" link size="small" @click="doTestSend(row)">测试发送</el-button>
                <el-button v-if="row.status === 'running'" link type="warning" size="small" @click="doPause(row)">暂停</el-button>
                <el-button v-if="row.status === 'paused'" link type="primary" size="small" @click="doResume(row)">恢复</el-button>
                <el-button v-if="['running', 'paused', 'scheduled'].includes(row.status)"
                           link type="danger" size="small" @click="doTerminate(row)">终止</el-button>
                <el-button v-if="['completed', 'terminated'].includes(row.status)" link size="small" @click="doCopy(row)">复制</el-button>
                <el-button v-if="['completed', 'terminated'].includes(row.status)"
                           link size="small" @click="$router.push(`/campaign/${row.id}`)">报表</el-button>
                <el-button v-if="['running', 'paused', 'scheduled'].includes(row.status)"
                           link size="small" @click="$router.push(`/campaign/${row.id}`)">监控</el-button>
                <el-button v-if="['draft', 'terminated'].includes(row.status)"
                           link type="danger" size="small" @click="doDelete(row)">删除</el-button>
              </template>
            </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        style="margin-top: 12px; justify-content: flex-end"
        layout="total, sizes, prev, pager, next"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import { analyticsApi, campaignApi } from '@/api'

interface CampaignRow {
  id: number
  name: string
  type: string
  time_range: string
  start_date: string
  end_date: string
  started_at?: string
  target_count: number
  deliver_rate: number
  open_rate: number
  click_rate: number
  victim_rate: number
  status: string
}

const router = useRouter()
const statusFilter = ref('')
const typeFilter = ref('')
const kw = ref('')
const dateRange = ref<[Date, Date] | null>(null)
const page = ref(1)
const pageSize = ref(10)
// 服务端返回的总条数（服务端分页）
const total = ref(0)
const selectedRows = ref<CampaignRow[]>([])

const TYPE_LABEL: Record<string, string> = {
  mail: '邮件钓鱼', sms: '短信钓鱼', social: '社交媒体', usb: 'USB实物',
}

const statCards = ref<{ key: string; label: string; value: string | number; sub: string; accent: string }[]>([])

const allRows = ref<CampaignRow[]>([])

// 状态筛选计数徽标（基于服务端返回的 stats 汇总，而非当前页数据）
const statusCounts = computed(() => {
  const valueOf = (key: string): string | number =>
    statCards.value.find((c) => c.key === key)?.value ?? 0
  return {
    all: valueOf(''),
    sending: valueOf('sending'),
    running: valueOf('running'),
    scheduled: valueOf('scheduled'),
    completed: valueOf('completed'),
    terminated: valueOf('terminated'),
  }
})

// 所有筛选（status/type/kw/日期范围）均由服务端过滤 + 分页，此处不做客户端切片
const pagedRows = computed(() => allRows.value)

// 筛选条件变化：重置页码并重新加载
watch([statusFilter, typeFilter, kw, dateRange], () => {
  page.value = 1
  load()
})
// 翻页 / 改页大小：服务端分页，重新请求
watch([page, pageSize], () => load())

interface CampaignListData {
  stats: { key: string; label: string; value: string | number; sub: string; accent: string }[]
  list: CampaignRow[]
  total: number
  page: number
  pageSize: number
}

function fmtDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

async function load() {
  try {
    const d = (await campaignApi.list({
      status: statusFilter.value,
      type: typeFilter.value,
      kw: kw.value,
      start_date: dateRange.value ? fmtDate(dateRange.value[0]) : undefined,
      end_date: dateRange.value ? fmtDate(dateRange.value[1]) : undefined,
      page: page.value,
      pageSize: pageSize.value,
    })) as CampaignListData | null
    if (d) {
      if (d.stats?.length) statCards.value = d.stats
      if (d.list) allRows.value = d.list
      total.value = d.total ?? 0
    }
  } catch {
    ElMessage.error('演练列表加载失败，请检查网络或后端服务')
  }
}

onMounted(load)

// 名称列状态副文（进行中按 started_at 计算天数）
function runningDays(row: CampaignRow): number {
  if (!row.started_at) return 1
  const started = new Date(row.started_at); started.setHours(0, 0, 0, 0)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.max(1, Math.round((today.getTime() - started.getTime()) / 86400000) + 1)
}
function statusSubText(row: CampaignRow): string {
  if (row.status === 'running') return `进行中 · 第${runningDays(row)}天`
  const sub: Record<string, string> = {
    sending: '发送中 · 批次投递中',
    scheduled: '待开始 · 筹备中',
    paused: '已暂停 · 可恢复',
    completed: '已完成 · 可导出报表',
    terminated: '已终止',
  }
  return sub[row.status] ?? ''
}

// 表格多选与批量导出
function onSelectionChange(selection: CampaignRow[]) {
  selectedRows.value = selection
}
async function batchExport() {
  if (!selectedRows.value.length) {
    ElMessage.warning('请先在表格中勾选要导出的演练')
    return
  }
  try {
    await analyticsApi.exportReport({
      kind: 'excel',
      scope: 'batch',
      campaign_ids: selectedRows.value.map(r => r.id),
    })
    ElMessage.success(`已导出 ${selectedRows.value.length} 场演练报表`)
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// 行操作：失败提示由 http 拦截器统一弹出，成功则重新拉取列表
async function doStart(row: CampaignRow) {
  try {
    await campaignApi.start(row.id)
    ElMessage.success('演练已启动')
    await load()
  } catch {
    /* 拦截器已提示错误 */
  }
}
async function doTestSend(row: CampaignRow) {
  let email = ''
  try {
    const { value } = await ElMessageBox.prompt(
      '输入白名单收件人邮箱（可多个，用逗号分隔），将按演练绑定的 SMTP 通道真实投递测试邮件',
      `测试发送「${row.name}」`,
      { confirmButtonText: '发送', cancelButtonText: '取消', inputPattern: /\S+/, inputErrorMessage: '请输入收件人邮箱' },
    )
    email = (value || '').trim()
  } catch {
    return // 用户取消
  }
  try {
    const res = (await campaignApi.testSend(row.id, email.split(/[,，\s]+/).filter(Boolean))) as {
      ok?: boolean; message?: string; results?: { to: string; ok: boolean; message: string }[]
    }
    const failed = (res.results || []).filter((r) => !r.ok)
    if (res.ok) {
      ElMessage.success(res.message || '测试邮件已发送')
    } else if (failed.length) {
      ElMessage.warning(
        failed.map((r) => `${r.to}：${r.message}`).join('；') || res.message || '部分收件人发送失败',
      )
    }
  } catch {
    /* 拦截器已提示错误 */
  }
}
async function doPause(row: CampaignRow) {
  try {
    await campaignApi.pause(row.id)
    ElMessage.success('演练已暂停')
    await load()
  } catch {
    /* 拦截器已提示错误 */
  }
}
async function doResume(row: CampaignRow) {
  try {
    await campaignApi.resume(row.id)
    ElMessage.success('演练已恢复')
    await load()
  } catch {
    /* 拦截器已提示错误 */
  }
}
async function doTerminate(row: CampaignRow) {
  try {
    await ElMessageBox.confirm('确认终止该演练？终止后不可撤销。', '终止演练', {
      confirmButtonText: '终止',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  try {
    await campaignApi.terminate(row.id)
    ElMessage.success('演练已终止')
    await load()
  } catch {
    /* 拦截器已提示错误 */
  }
}
function doEdit(row: CampaignRow) {
  ElMessage.info(`已进入演练向导（编辑「${row.name}」）`)
  router.push('/campaign/create')
}
async function doCopy(row: CampaignRow) {
  try {
    await campaignApi.duplicateCampaign(row.id)
    ElMessage.success(`已复制演练「${row.name}」，新草稿已生成`)
    await load()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}
async function doDelete(row: CampaignRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除演练「${row.name}」？将级联清除其目标、统计与行为事件，此操作不可恢复。`,
      '删除演练',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await campaignApi.deleteCampaign(row.id)
    ElMessage.success(`演练「${row.name}」已删除`)
    await load()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}
</script>

<style scoped lang="scss">
.stat-mini {
  .stat-title { font-size: 12px; color: var(--color-text-secondary); }
  .stat-value { font-size: 24px; font-weight: 600; margin-top: 6px; }
  .stat-sub { font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px; }
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.filter-count {
  margin-left: 4px;
  opacity: 0.75;
  font-weight: 500;
}
.name-sub {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.stage-progress {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.stage-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stage-label {
  width: 32px;
  font-size: 11px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.stage-val {
  width: 36px;
  text-align: right;
  font-size: 11px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
</style>
