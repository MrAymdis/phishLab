<template>
  <div class="page-container">
    <PageHeader title="API开放平台">
      <template #actions>
        <el-button size="small">API控制台跳转</el-button>
        <el-button size="small" type="primary" :icon="Download">接入文档下载</el-button>
      </template>
    </PageHeader>

    <div class="card" style="margin: 16px 16px 16px">
      <el-tabs v-model="tab">
        <el-tab-pane label="API概览" name="overview">
          <el-row :gutter="12" style="margin-bottom: 12px">
            <el-col :span="6" v-for="s in overviewStats" :key="s.title">
              <StatCard :title="s.title" :value="s.value" :suffix="s.suffix" :accent="s.accent" :sub="s.sub" />
            </el-col>
          </el-row>

          <el-row :gutter="12">
            <el-col :span="4">
              <div class="card card-teal">
                <div class="card-title">API分类</div>
                <div v-for="c in categories" :key="c.key" class="cat-row"
                  :class="{ active: activeCat === c.key }" @click="activeCat = c.key">
                  <span class="cat-icon">{{ c.icon }}</span>
                  <span class="cat-name">{{ c.name }}</span>
                  <el-tag size="small" :type="c.tagType">{{ c.count }}</el-tag>
                </div>
              </div>
            </el-col>
            <el-col :span="20">
              <div class="card card-blue">
                <div class="card-title">近7天调用趋势</div>
                <BaseChart :option="trendChart" height="300px" />
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="应用管理" name="apps">
          <div class="toolbar">
            <el-button type="primary" size="small" :icon="Plus" @click="createAppVisible = true">创建应用</el-button>
            <el-input v-model="appKw" size="small" placeholder="搜索应用名称/AppID" clearable style="width: 240px" />
          </div>

          <el-table :data="filteredApps" size="small" style="margin-top: 12px">
            <el-table-column label="应用名称" min-width="160">
              <template #default="{ row }">
                <div style="display:flex;align-items:center;gap:8px">
                  <div class="app-avatar" :style="{ background: row.color }">{{ row.name[0] }}</div>
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="AppID" width="220" prop="app_id" />
            <el-table-column label="AppSecret" width="220">
              <template #default="{ row }">
                <span v-if="row._show">{{ row.secret }}</span>
                <span v-else>· · · · · · · · · · · · · · · ·</span>
                <el-link style="margin-left:6px" @click="row._show = !row._show">{{ row._show ? '隐藏' : '显示' }}</el-link>
                <el-link type="warning" style="margin-left:4px" @click="regenSecret(row)">重生成</el-link>
              </template>
            </el-table-column>
            <el-table-column label="权限 scope" min-width="200">
              <template #default="{ row }">
                <el-tag v-for="s in row.scopes.slice(0,3)" :key="s" size="small" effect="plain" style="margin-right:4px">{{ s }}</el-tag>
                <el-tag v-if="row.scopes.length > 3" size="small">+{{ row.scopes.length - 3 }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="调用次数" width="100" align="right">
              <template #default="{ row }">{{ row.calls.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'active' ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="150" prop="created_at" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link size="small" type="primary" @click="regenSecret(row)">编辑密钥</el-button>
                <el-button link size="small" type="primary" @click="openEdit(row)">权限编辑</el-button>
                <el-button link size="small" :type="row.status === 'active' ? 'warning' : 'success'" @click="toggleStatus(row)">
                  {{ row.status === 'active' ? '禁用' : '启用' }}
                </el-button>
                <el-button link size="small" type="danger" @click="removeApp(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="API文档" name="docs">
          <el-alert :closable="false" show-icon type="info" class="docs-hint"
            title="接入步骤：① 管理端「应用管理」创建应用并勾选 scope → ② POST /openapi/v1/oauth/token 用 AppID/AppSecret 换取 access_token（2 小时有效）→ ③ 携带 Authorization: Bearer &lt;token&gt; 调用业务接口。应用 scope 决定可调用的接口域，停用应用立即生效。" />
          <div class="docs-layout">
            <div class="docs-tree">
              <el-tree :data="apiTree" node-key="id" :props="{ label: 'name', children: 'children' }"
                :expand-on-click-node="false" :default-expanded-keys="['campaign', 'auth']"
                :current-node-key="currentApi?.id" @node-click="onApiClick" />
            </div>
            <div class="docs-content" v-if="currentApi">
              <div class="api-head">
                <el-tag :type="methodColor(currentApi.method)" effect="dark" size="small">{{ currentApi.method }}</el-tag>
                <code class="api-url">{{ currentApi.path }}</code>
                <h3 class="api-name">{{ currentApi.name }}</h3>
                <p class="api-desc">{{ currentApi.desc }}</p>
                <el-alert v-if="currentApi.note" :title="currentApi.note" type="warning" :closable="false" show-icon
                  style="margin-top: 10px" />
              </div>

              <div class="card card-blue nested-card" style="margin-top: 12px">
                <div class="card-title">请求参数</div>
                <el-table :data="currentApi.params || []" size="small" border>
                  <el-table-column label="参数名" prop="name" width="140">
                    <template #default="{ row }">
                      <span :style="{ color: row.required ? '#a32d2d' : '' }">{{ row.name }}</span>
                      <sup v-if="row.required" style="color:#a32d2d">*</sup>
                    </template>
                  </el-table-column>
                  <el-table-column label="类型" prop="type" width="110" />
                  <el-table-column label="必填" width="70">
                    <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
                  </el-table-column>
                  <el-table-column label="默认值" prop="default" width="100" />
                  <el-table-column label="描述" prop="desc" />
                </el-table>
              </div>

              <div class="card card-green nested-card" style="margin-top: 12px" v-if="currentApi.method === 'POST'">
                <div class="card-title">
                  请求体示例
                  <el-button size="small" link type="primary" @click="copyJson(currentApi.req_example)">复制</el-button>
                </div>
                <pre class="json-block">{{ JSON.stringify(currentApi.req_example, null, 2) }}</pre>
              </div>
              <div class="card card-green nested-card" style="margin-top: 12px" v-else>
                <div class="card-title">
                  请求示例（URL + Query）
                  <el-button size="small" link type="primary" @click="copyText(currentApi.url_example || '')">复制</el-button>
                </div>
                <pre class="json-block">{{ currentApi.url_example }}</pre>
              </div>

              <div class="card card-orange nested-card" style="margin-top: 12px">
                <div class="card-title">
                  响应示例
                  <el-button size="small" link type="primary" @click="copyJson(currentApi.res_example)">复制</el-button>
                </div>
                <pre class="json-block">{{ JSON.stringify(currentApi.res_example, null, 2) }}</pre>
              </div>

              <div class="card card-red nested-card" style="margin-top: 12px">
                <div class="card-title">错误码</div>
                <el-table :data="currentApi.errors || []" size="small" border>
                  <el-table-column label="错误码" prop="code" width="120" />
                  <el-table-column label="说明" prop="message" />
                  <el-table-column label="HTTP状态" prop="http" width="110" />
                </el-table>
              </div>
            </div>
            <el-alert v-else type="info" :closable="false" show-icon title="请从左侧选择一个接口查看详情" style="flex:1" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="调用日志" name="logs">
          <el-row :gutter="12" style="margin-bottom: 12px">
            <el-col :span="8" v-for="m in logMiniCards" :key="m.title">
              <div class="card" :class="`card-${m.accent}`">
                <div class="log-mini-title">{{ m.title }}</div>
                <div class="log-mini-value">{{ m.value }}</div>
              </div>
            </el-col>
          </el-row>

          <div class="toolbar">
            <el-select v-model="logFilter.app" size="small" placeholder="全部应用" clearable style="width: 160px">
              <el-option v-for="a in apps" :key="a.id" :label="a.name" :value="a.id" />
            </el-select>
            <el-select v-model="logFilter.method" size="small" placeholder="方法" style="width: 110px">
              <el-option label="全部" value="" />
              <el-option label="GET" value="GET" />
              <el-option label="POST" value="POST" />
              <el-option label="PUT" value="PUT" />
              <el-option label="DELETE" value="DELETE" />
            </el-select>
            <el-select v-model="logFilter.status" size="small" placeholder="状态" style="width: 110px">
              <el-option label="全部" value="" />
              <el-option label="2xx" value="2xx" />
              <el-option label="4xx" value="4xx" />
              <el-option label="5xx" value="5xx" />
            </el-select>
            <el-date-picker v-model="logFilter.range" type="datetimerange" size="small" range-separator="至"
              start-placeholder="开始" end-placeholder="结束" />
            <el-input v-model="logFilter.kw" size="small" placeholder="搜索路径/IP" clearable style="width: 200px" />
            <el-button size="small" type="primary" @click="loadLogs(1)">查询</el-button>
          </div>

          <el-table :data="logs" size="small" style="margin-top: 12px">
            <el-table-column label="时间" prop="time" width="170" />
            <el-table-column label="应用" prop="app_name" width="120" />
            <el-table-column label="方法" width="70">
              <template #default="{ row }">
                <el-tag size="small" :type="methodTag(row.method)" effect="dark">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="API路径" prop="path" min-width="220" show-overflow-tooltip />
            <el-table-column label="状态码" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTag(row.status_code)">
                  {{ row.status_code }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="响应时间" width="100" align="right">
              <template #default="{ row }">
                <span :style="{ color: row.response_ms > 500 ? '#a32d2d' : '', fontWeight: row.response_ms > 500 ? 600 : '' }">
                  {{ row.response_ms }} ms
                </span>
              </template>
            </el-table-column>
            <el-table-column label="请求IP" prop="ip" width="130" />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openLogDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination style="margin-top: 12px; justify-content: flex-end"
            layout="total, sizes, prev, pager, next" :total="logTotal" :page-sizes="[10,20,50,100]"
            :page-size="logPage.pageSize" :current-page="logPage.page"
            @current-change="loadLogs" @size-change="onLogSize" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="createAppVisible" :title="editingId ? '编辑应用' : '创建应用'" width="560px">
      <el-form label-width="100px" size="small">
        <el-form-item label="应用名称" required>
          <el-input v-model="newApp.name" placeholder="例如：内部OA系统集成" />
        </el-form-item>
        <el-form-item label="应用描述">
          <el-input v-model="newApp.desc" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="权限范围">
          <el-checkbox-group v-model="newApp.scopes">
            <div v-for="g in scopeGroups" :key="g.name" class="scope-group">
              <div class="scope-group-name">{{ g.name }}</div>
              <el-checkbox v-for="s in g.items" :key="s" :value="s" style="margin-right:12px">{{ s }}</el-checkbox>
            </div>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="IP白名单">
          <el-input v-model="newApp.ip_whitelist" type="textarea" :rows="3" placeholder="每行一个IP，例如：&#10;10.0.0.1&#10;192.168.1.0/24" />
        </el-form-item>
        <el-form-item label="回调URL">
          <el-input v-model="newApp.callback_url" placeholder="https://your-app.com/oauth/callback" />
        </el-form-item>
        <el-form-item label="Rate Limit">
          <el-input-number v-model="newApp.rate_limit" :min="10" :max="100000" :step="10" />
          <span style="margin-left:8px;color:#8c8c8c">/ 分钟</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createAppVisible = false">取消</el-button>
        <el-button type="primary" @click="submitApp">{{ editingId ? '确认保存' : '确认创建' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logDetailVisible" title="调用详情" width="720px" top="4vh">
      <div v-if="logDetail" class="log-detail">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="时间">{{ logDetail.time }}</el-descriptions-item>
          <el-descriptions-item label="请求ID">{{ logDetail.req_id }}</el-descriptions-item>
          <el-descriptions-item label="应用">{{ logDetail.app_name }}</el-descriptions-item>
          <el-descriptions-item label="IP">{{ logDetail.ip }}</el-descriptions-item>
          <el-descriptions-item label="方法 / 状态">
            <el-tag size="small" :type="methodTag(logDetail.method)" effect="dark">{{ logDetail.method }}</el-tag>
            <el-tag size="small" :type="statusTag(logDetail.status_code)" style="margin-left:6px">{{ logDetail.status_code }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="响应时间">{{ logDetail.response_ms }} ms</el-descriptions-item>
          <el-descriptions-item label="路径" :span="2"><code>{{ logDetail.path }}</code></el-descriptions-item>
        </el-descriptions>

        <el-tabs style="margin-top: 16px">
          <el-tab-pane label="请求头" name="req_headers">
            <el-table :data="tableize(logDetail.req_headers)" size="small" border>
              <el-table-column label="Name" prop="key" width="200" />
              <el-table-column label="Value" prop="val" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="请求体" name="req_body">
            <pre class="json-block">{{ JSON.stringify(logDetail.req_body, null, 2) }}</pre>
          </el-tab-pane>
          <el-tab-pane label="响应头" name="res_headers">
            <el-table :data="tableize(logDetail.res_headers)" size="small" border>
              <el-table-column label="Name" prop="key" width="200" />
              <el-table-column label="Value" prop="val" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="响应体" name="res_body">
            <pre class="json-block">{{ JSON.stringify(logDetail.res_body, null, 2) }}</pre>
          </el-tab-pane>
          <el-tab-pane label="错误信息" name="error" v-if="logDetail.error">
            <el-alert type="error" :closable="false" show-icon :title="logDetail.error.code" :description="logDetail.error.message" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, shallowRef, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import { Plus, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { openapiApi } from '@/api'
import type { OpenApiLogItem, OpenApiStats } from '@/api'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import BaseChart from '@/components/base/BaseChart.vue'

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

const tab = ref<'overview' | 'apps' | 'docs' | 'logs'>('overview')

// ---------- API概览（真实统计） ----------
const statsData = ref<OpenApiStats | null>(null)

const overviewStats = computed(() => [
  { title: '总调用数', value: statsData.value?.total_calls.toLocaleString() ?? '—', suffix: ' 次', sub: '含 token 换取', accent: 'blue' as Accent },
  { title: '活跃应用数', value: String(statsData.value?.active_apps ?? '—'), suffix: ' 个', sub: '当前启用', accent: 'teal' as Accent },
  { title: '调用成功率', value: statsData.value ? statsData.value.success_rate.toFixed(2) : '—', suffix: '%', sub: '2xx 占比', accent: 'green' as Accent },
  { title: '平均响应时间', value: String(statsData.value?.avg_latency ?? '—'), suffix: ' ms', sub: '整体均值', accent: 'orange' as Accent },
])

const categories = [
  { key: 'campaign', name: '演练管理', icon: '🎯', count: 5, tagType: 'primary' as const },
  { key: 'user', name: '用户管理', icon: '👥', count: 2, tagType: 'success' as const },
  { key: 'template', name: '模板管理', icon: '📧', count: 2, tagType: 'warning' as const },
  { key: 'report', name: '数据报表', icon: '📊', count: 3, tagType: 'info' as const },
  { key: 'mail_report', name: '举报管理', icon: '🛡️', count: 1, tagType: 'danger' as const },
  { key: 'system', name: '系统管理', icon: '⚙️', count: 1, tagType: 'info' as const },
]
const activeCat = ref('campaign')

const trendChart = shallowRef<EChartsOption>({
  tooltip: { trigger: 'axis' },
  legend: { data: ['调用次数', '成功率%'], top: 0, textStyle: { fontSize: 11 } },
  grid: { left: 48, right: 52, top: 32, bottom: 28 },
  xAxis: { type: 'category', data: [] },
  yAxis: [
    { type: 'value', name: '调用次数', axisLabel: { fontSize: 11 } },
    { type: 'value', name: '%', min: 95, max: 100, axisLabel: { fontSize: 11 } },
  ],
  series: [
    { name: '调用次数', type: 'bar', barWidth: 18, data: [],
      itemStyle: { color: '#378ADD', borderRadius: [4, 4, 0, 0] } },
    { name: '成功率%', type: 'line', yAxisIndex: 1, smooth: true, data: [],
      itemStyle: { color: '#1d9e75' }, lineStyle: { width: 2 },
      areaStyle: { color: 'rgba(29,158,117,0.12)' } },
  ],
})

async function loadStats() {
  try {
    const s = await openapiApi.stats()
    statsData.value = s
    trendChart.value = {
      tooltip: { trigger: 'axis' },
      legend: { data: ['调用次数', '成功率%'], top: 0, textStyle: { fontSize: 11 } },
      grid: { left: 48, right: 52, top: 32, bottom: 28 },
      xAxis: { type: 'category', data: s.trend.map(t => t.date.slice(5)) },
      yAxis: [
        { type: 'value', name: '调用次数', axisLabel: { fontSize: 11 } },
        { type: 'value', name: '%', min: 95, max: 100, axisLabel: { fontSize: 11 } },
      ],
      series: [
        { name: '调用次数', type: 'bar', barWidth: 18, data: s.trend.map(t => t.calls),
          itemStyle: { color: '#378ADD', borderRadius: [4, 4, 0, 0] } },
        { name: '成功率%', type: 'line', yAxisIndex: 1, smooth: true, data: s.trend.map(t => t.success_rate),
          itemStyle: { color: '#1d9e75' }, lineStyle: { width: 2 },
          areaStyle: { color: 'rgba(29,158,117,0.12)' } },
      ],
    }
  } catch {
    // 概览失败保留占位，不打断页面
  }
}

const appKw = ref('')
const appColors = ['#378ADD', '#7f77dd', '#1d9e75', '#d85a30', '#a32d2d', '#0d9488']
const apps = ref<any[]>([])
const filteredApps = computed(() => {
  const kw = appKw.value.trim().toLowerCase()
  if (!kw) return apps.value
  return apps.value.filter(a => a.name.toLowerCase().includes(kw) || a.app_id.toLowerCase().includes(kw))
})

/** 后端应用 → 视图行（app_secret 为掩码，calls ← call_count） */
function mapApp(a: any, i: number) {
  return reactive({
    id: a.id,
    name: a.name,
    description: a.description ?? '',
    app_id: a.app_id,
    secret: a.app_secret || '',
    ip_whitelist: Array.isArray(a.ip_whitelist) ? a.ip_whitelist : [],
    callback_url: a.callback_url ?? '',
    rate_limit: a.rate_limit ?? 60,
    calls: a.call_count ?? 0,
    status: a.status,
    created_at: a.created_at ?? '',
    scopes: Array.isArray(a.scopes) ? a.scopes : [],
    color: appColors[i % appColors.length],
    _show: false,
  })
}

async function loadApps() {
  try {
    const data = (await openapiApi.apps()) as any[]
    if (Array.isArray(data)) apps.value = data.map(mapApp)
  } catch {
    ElMessage.warning('应用列表加载失败')
  }
}

async function regenSecret(row: any) {
  try {
    const res = await openapiApi.regenSecret(row.id)
    row.secret = res.app_secret
    row._show = true
    ElMessage.success('AppSecret 已重新生成，旧密钥立即失效')
  } catch {
    // 失败提示由 http 拦截器处理
  }
}

async function toggleStatus(row: any) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  try {
    await openapiApi.toggleApp(row.id, next)
    row.status = next
    ElMessage.success(`应用已${next === 'active' ? '启用' : '禁用'}`)
  } catch {
    // 失败提示由 http 拦截器处理
  }
}

async function removeApp(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除应用「${row.name}」？其调用日志将一并删除。`, '删除应用',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await openapiApi.deleteApp(row.id)
    ElMessage.success('应用已删除')
    await loadApps()
  } catch (err: any) {
    if (err !== 'cancel') return
  }
}

const createAppVisible = ref(false)
const editingId = ref<number | null>(null)
const newApp = reactive({ name: '', desc: '', scopes: [] as string[], ip_whitelist: '', callback_url: '', rate_limit: 1000 })
const scopeGroups = [
  { name: '演练管理', items: ['campaign'] },
  { name: '数据报表', items: ['report'] },
  { name: '用户管理', items: ['user'] },
  { name: '模板管理', items: ['template'] },
  { name: '举报管理', items: ['mail_report'] },
  { name: '系统信息', items: ['system'] },
]

function openEdit(row: any) {
  editingId.value = row.id
  newApp.name = row.name
  newApp.desc = row.description || ''
  newApp.scopes = [...(row.scopes || [])]
  newApp.ip_whitelist = (row.ip_whitelist || []).join('\n')
  newApp.callback_url = row.callback_url || ''
  newApp.rate_limit = row.rate_limit || 60
  createAppVisible.value = true
}

async function submitApp() {
  if (!newApp.name) return ElMessage.warning('请填写应用名称')
  const payload = {
    name: newApp.name,
    description: newApp.desc,
    scopes: newApp.scopes,
    ip_whitelist: newApp.ip_whitelist.split('\n').map(s => s.trim()).filter(Boolean),
    callback_url: newApp.callback_url,
    rate_limit: newApp.rate_limit,
  }
  try {
    let created: { id: number; app_secret: string } | null = null
    if (editingId.value) {
      await openapiApi.updateApp(editingId.value, payload)
      ElMessage.success('应用已更新')
    } else {
      const res = await openapiApi.createApp(payload)
      created = res
      ElMessage.success('应用已创建，AppID/Secret 请妥善保管')
    }
    createAppVisible.value = false
    editingId.value = null
    await loadApps()
    // 完整 Secret 仅创建时返回：拉取（掩码）后回填明文便于立即展示
    if (created) {
      const row = apps.value.find(x => x.id === created!.id)
      if (row) {
        row.secret = created.app_secret
        row._show = true
      }
    }
  } catch {
    // 失败提示由 http 拦截器处理，保持弹窗打开可重试
  }
}

interface ApiNode {
  id: string; name: string; method?: Method; path?: string; desc?: string; note?: string;
  children?: ApiNode[]; params?: any[]; url_example?: string;
  req_example?: any; res_example?: any; errors?: any[];
}
// 网关真实接口清单（契约源：server/app/modules/openapi_mod/{router,biz}.py）
// 业务接口统一携带 Authorization: Bearer <access_token>（先经 POST /openapi/v1/oauth/token 换取）
const AUTH_PARAM = {
  name: 'Authorization', type: 'header', required: true, default: '-',
  desc: 'Bearer <access_token>（oauth/token 换取，2 小时有效）',
}
// 网关通用错误（fail-closed，各业务接口一致）
const GATEWAY_ERRORS = [
  { code: '40101', message: '缺少 Bearer access_token', http: '401' },
  { code: '40102', message: 'access_token 无效或已过期', http: '401' },
  { code: '40302', message: '应用不存在/禁用、scope 不足或调用 IP 不在白名单', http: '403' },
  { code: '42902', message: '超过限流阈值（应用 rate_limit 次/分钟）', http: '429' },
]
const DETAIL_ERRORS = [...GATEWAY_ERRORS, { code: '10404', message: '资源不存在（ID 无效）', http: '404' }]
const PARAM_ERRORS = [...GATEWAY_ERRORS, { code: '10001', message: '参数校验失败（如 auth_confirmed 非 true）', http: '200' }]

const apiTree: ApiNode[] = [
  { id: 'auth', name: '认证', children: [
    { id: 'a1', name: '换取 access_token', method: 'POST', path: '/openapi/v1/oauth/token',
      desc: 'OAuth2 client_credentials 模式：AppID/AppSecret 换取 2 小时有效 access_token，scope 为应用已授权域',
      params: [
        { name: 'grant_type', type: 'string', required: true, default: 'client_credentials', desc: '固定值' },
        { name: 'app_id', type: 'string', required: true, default: '-', desc: '应用 AppID（app_ 前缀）' },
        { name: 'app_secret', type: 'string', required: true, default: '-', desc: '应用 AppSecret（sk_live_ 前缀，仅创建/重生成时返回明文）' },
      ],
      req_example: { grant_type: 'client_credentials', app_id: 'app_3f9a2c1d', app_secret: 'sk_live_xxxx' },
      res_example: { code: 0, message: 'ok', data: { access_token: 'eyJhbGciOiJIUzI1NiIs...', expires_in: 7200, scope: 'campaign report user template mail_report system' } },
      errors: [
        { code: '40302', message: '应用不存在/禁用或 AppSecret 校验失败', http: '403' },
        { code: '10001', message: '请求体缺少必填字段或格式错误', http: '200' },
      ],
    },
  ]},
  { id: 'campaign', name: '演练管理（scope: campaign）', children: [
    { id: 'c1', name: '演练列表', method: 'GET', path: '/openapi/v1/campaigns',
      desc: '分页获取演练列表（含实时统计），支持按状态筛选',
      params: [
        AUTH_PARAM,
        { name: 'status', type: 'string', required: false, default: '-', desc: 'draft/scheduled/sending/running/paused/completed/terminated' },
        { name: 'page', type: 'int', required: false, default: '1', desc: '页码' },
        { name: 'page_size', type: 'int', required: false, default: '20', desc: '每页数量（≤100）' },
      ],
      url_example: '/openapi/v1/campaigns?status=completed&page=1&page_size=20',
      res_example: { code: 0, message: 'ok', data: { total: 2, page: 1, page_size: 20, list: [
        { id: 101, name: 'Q3全员防钓鱼演练', type: 'mail', status: 'completed', target_count: 200,
          schedule_type: 'timed', schedule_at: '2026-08-30 09:00:00', started_at: '2026-08-30 09:05:00',
          ended_at: '2026-09-06 09:05:00', created_at: '2026-08-28 10:00:00',
          stats: { delivered: 198, open: 120, click: 45, submit: 12, attach: 3, report: 8 } },
      ] } },
      errors: GATEWAY_ERRORS,
    },
    { id: 'c2', name: '演练详情', method: 'GET', path: '/openapi/v1/campaigns/{cid}',
      desc: '演练详情：基础信息 + 实时统计 + 中招数/中招率（中招 = 提交 + 附件运行）',
      params: [AUTH_PARAM, { name: 'cid', type: 'int', required: true, default: '-', desc: '演练ID（路径参数）' }],
      url_example: '/openapi/v1/campaigns/101',
      res_example: { code: 0, message: 'ok', data: {
        id: 101, name: 'Q3全员防钓鱼演练', description: '模拟 HR 薪酬调整通知', type: 'mail', status: 'completed',
        target_count: 200, schedule_type: 'timed', schedule_at: '2026-08-30 09:00:00',
        batch_count: 2, batch_interval_min: 30, training_policy: 'redirect',
        started_at: '2026-08-30 09:05:00', ended_at: '2026-09-06 09:05:00', created_at: '2026-08-28 10:00:00',
        stats: { delivered: 198, open: 120, click: 45, submit: 12, attach: 3, report: 8 },
        victim_count: 15, victim_rate: 7.5 } },
      errors: DETAIL_ERRORS,
    },
    { id: 'c3', name: '创建演练草稿', method: 'POST', path: '/openapi/v1/campaigns',
      desc: '创建演练（红线 4：auth_confirmed 必填 true）。产物始终为草稿，API 不提供启动/发送动作',
      note: '红线约束：auth_confirmed 必须为 true；schedule_type=now 创建为 draft，=timed 创建为 scheduled；发送启动仅在平台内人工操作。中招明细不返回任何口令内容（红线 1）。',
      params: [
        AUTH_PARAM,
        { name: 'name', type: 'string', required: true, default: '-', desc: '演练名称（≤128 字符）' },
        { name: 'type', type: 'string', required: true, default: '-', desc: 'mail / sms / social（企微）/ usb' },
        { name: 'template_id', type: 'int', required: false, default: '-', desc: '邮件模板ID' },
        { name: 'landing_page_id', type: 'int', required: false, default: '-', desc: '落地页ID' },
        { name: 'channel_id', type: 'int', required: false, default: '-', desc: '投递通道ID' },
        { name: 'sender_profile_id', type: 'int', required: false, default: '-', desc: '伪装发件人ID' },
        { name: 'target_mode', type: 'string', required: false, default: 'dept', desc: 'dept/tag/csv/mix（圈选快照见 target_snapshot）' },
        { name: 'schedule_type', type: 'string', required: false, default: 'now', desc: 'now=草稿 / timed=定时计划' },
        { name: 'schedule_at', type: 'datetime', required: false, default: '-', desc: 'timed 时的发送时间（ISO 格式）' },
        { name: 'ended_at', type: 'datetime', required: false, default: '-', desc: '演练结束时间，留空按投递后 7 天' },
        { name: 'batch_count', type: 'int', required: false, default: '1', desc: '批次数量（≥1）' },
        { name: 'batch_interval_min', type: 'int', required: false, default: '0', desc: '批次间隔分钟' },
        { name: 'randomize_content', type: 'bool', required: false, default: 'false', desc: '多模板随机轮换' },
        { name: 'time_jitter_sec', type: 'int', required: false, default: '0', desc: '投递时刻随机抖动 0~600 秒' },
        { name: 'training_policy', type: 'string', required: false, default: 'none', desc: '中招教育策略 redirect/popup/none/url' },
        { name: 'training_redirect_url', type: 'string', required: false, default: '-', desc: 'url 模式跳转目标' },
        { name: 'attachment_ids', type: 'int[]', required: false, default: '[]', desc: '附件载荷ID（直发模式）' },
        { name: 'course_ids', type: 'int[]', required: false, default: '[]', desc: '关联培训课程' },
        { name: 'auth_confirmed', type: 'bool', required: true, default: '-', desc: '授权确认，必须为 true（红线 4）' },
        { name: 'auth_snapshot', type: 'string[]', required: false, default: '[]', desc: '授权勾选项快照（企微演练另有必填项）' },
      ],
      req_example: {
        name: 'Q3全员防钓鱼演练', description: '模拟 HR 薪酬调整通知', type: 'mail',
        template_id: 12, landing_page_id: 3, channel_id: 2, sender_profile_id: 1,
        target_mode: 'dept', target_snapshot: { dept_ids: [5, 6] },
        schedule_type: 'timed', schedule_at: '2026-09-01T09:00:00', ended_at: '2026-09-08T09:00:00',
        batch_count: 2, batch_interval_min: 30, randomize_content: true, time_jitter_sec: 60,
        training_policy: 'redirect', training_redirect_url: 'https://edu.example.com/security',
        attachment_ids: [], course_ids: [1], force_training_rules: [],
        auth_confirmed: true, auth_snapshot: ['mail:authorized_internal_drill'],
      },
      res_example: { code: 0, message: 'ok', data: { id: 101 } },
      errors: PARAM_ERRORS,
    },
    { id: 'c4', name: '演练目标明细', method: 'GET', path: '/openapi/v1/campaigns/{cid}/targets',
      desc: '目标员工及中招状态分页明细（中招 = 提交 + 附件运行），支持只看中招',
      params: [
        AUTH_PARAM,
        { name: 'cid', type: 'int', required: true, default: '-', desc: '演练ID（路径参数）' },
        { name: 'victim_only', type: 'bool', required: false, default: 'false', desc: '仅返回中招（提交或附件运行）' },
        { name: 'page', type: 'int', required: false, default: '1', desc: '页码' },
        { name: 'page_size', type: 'int', required: false, default: '20', desc: '每页数量（≤100）' },
      ],
      url_example: '/openapi/v1/campaigns/101/targets?victim_only=true&page=1&page_size=20',
      res_example: { code: 0, message: 'ok', data: { total: 1, page: 1, page_size: 20, list: [
        { id: 5001, user_id: 301, name: '张三', email: 'zhangsan@corp.com', dept: '财务部',
          send_status: 'delivered', sent_at: '2026-08-30 09:05:12', open_count: 2, click_count: 1,
          submit_flag: true, submit_at: '2026-08-30 09:12:40', attach_run_count: 0,
          report_flag: true, victim: true },
      ] } },
      errors: DETAIL_ERRORS,
    },
    { id: 'c5', name: '演练结果报表', method: 'GET', path: '/openapi/v1/campaigns/{cid}/report',
      desc: '结果报表：指标卡 + 转化漏斗 + 中招明细 TOP20 + 近 14 天日趋势（口径与内部报表一致）',
      params: [AUTH_PARAM, { name: 'cid', type: 'int', required: true, default: '-', desc: '演练ID（路径参数）' }],
      url_example: '/openapi/v1/campaigns/101/report',
      res_example: { code: 0, message: 'ok', data: {
        campaign: { id: 101, name: 'Q3全员防钓鱼演练', status: 'completed' },
        metrics: [
          { title: '发送数', value: 200 }, { title: '打开数', value: 120, rate: 60.0 },
          { title: '点击数', value: 45, rate: 22.5 }, { title: '中招数', value: 15, rate: 7.5 },
          { title: '举报数', value: 8, rate: 4.0 }, { title: '综合得分', value: 85 },
        ],
        funnel: [
          { stage: '发送', count: 200 }, { stage: '打开', count: 120, rate: 60.0 },
          { stage: '点击', count: 45, rate: 37.5 }, { stage: '中招', count: 15, rate: 33.3 },
        ],
        victims_top: [
          { name: '张三', email: 'zhangsan@corp.com', dept: '财务部', submit: true, attach_run: 0, click_count: 1, open_count: 2 },
        ],
        daily: { labels: ['2026-08-29', '2026-08-30'], open: [10, 20], click: [3, 5], victim: [1, 2] } } },
      errors: DETAIL_ERRORS,
    },
  ]},
  { id: 'report', name: '数据报表（scope: report）', children: [
    { id: 'r1', name: '平台概览指标', method: 'GET', path: '/openapi/v1/reports/overview',
      desc: '平台级概览：演练总数/进行中、员工数、部门数、累计中招数、举报数、最近演练时间',
      params: [AUTH_PARAM],
      url_example: '/openapi/v1/reports/overview',
      res_example: { code: 0, message: 'ok', data: { campaign_total: 36, campaign_running: 2,
        emp_total: 1250, dept_total: 24, victim_total: 87, report_total: 132,
        last_campaign_at: '2026-08-30 09:05:00' } },
      errors: GATEWAY_ERRORS,
    },
    { id: 'r2', name: '中招趋势', method: 'GET', path: '/openapi/v1/reports/trend',
      desc: '按天聚合的行为趋势（victim = 提交 + 附件运行），时间窗口 7d/month/quarter',
      params: [AUTH_PARAM, { name: 'range', type: 'string', required: false, default: 'month', desc: '7d / month / quarter' }],
      url_example: '/openapi/v1/reports/trend?range=7d',
      res_example: { code: 0, message: 'ok', data: { labels: ['2026-08-24', '2026-08-25'],
        open: [30, 45], click: [8, 12], victim: [2, 5] } },
      errors: GATEWAY_ERRORS,
    },
    { id: 'r3', name: '部门中招对比', method: 'GET', path: '/openapi/v1/reports/department',
      desc: '按部门聚合的横向对比（投递时间窗口；窗口内无投递时回退全量，与内部报表一致）',
      params: [AUTH_PARAM, { name: 'range', type: 'string', required: false, default: 'month', desc: '7d / month / quarter' }],
      url_example: '/openapi/v1/reports/department?range=month',
      res_example: { code: 0, message: 'ok', data: { rows: [
        { dept: '财务部', targetCount: 86, victim: 9, report: 4, total: 92,
          openRate: 65.1, clickRate: 22.1, submitRate: 10.5, reportRate: 4.7 } ] } },
      errors: GATEWAY_ERRORS,
    },
  ]},
  { id: 'user', name: '用户管理（scope: user）', children: [
    { id: 'u1', name: '员工列表', method: 'GET', path: '/openapi/v1/users',
      desc: '员工列表（含行为统计：参与演练数/中招次数/打开/点击），支持关键字与部门筛选',
      params: [
        AUTH_PARAM,
        { name: 'kw', type: 'string', required: false, default: '-', desc: '姓名/邮箱关键字（不区分大小写）' },
        { name: 'dept_id', type: 'int', required: false, default: '-', desc: '部门筛选' },
        { name: 'page', type: 'int', required: false, default: '1', desc: '页码' },
        { name: 'page_size', type: 'int', required: false, default: '20', desc: '每页数量（≤100）' },
      ],
      url_example: '/openapi/v1/users?kw=张&dept_id=6&page=1&page_size=20',
      res_example: { code: 0, message: 'ok', data: { total: 1, page: 1, page_size: 20, list: [
        { id: 301, emp_no: 'E1024', name: '张三', email: 'zhangsan@corp.com', dept: '财务部',
          position: '会计', status: 'active', behavior: { campaigns: 3, victim: 1, open: 5, click: 2 } },
      ] } },
      errors: GATEWAY_ERRORS,
    },
    { id: 'u2', name: '员工详情', method: 'GET', path: '/openapi/v1/users/{uid}',
      desc: '员工详情：档案 + 行为统计 + 最近 10 条行为事件（open/click/submit/attach_run）',
      params: [AUTH_PARAM, { name: 'uid', type: 'int', required: true, default: '-', desc: '员工ID（路径参数）' }],
      url_example: '/openapi/v1/users/301',
      res_example: { code: 0, message: 'ok', data: {
        id: 301, emp_no: 'E1024', name: '张三', email: 'zhangsan@corp.com', dept: '财务部',
        position: '会计', status: 'active', behavior: { campaigns: 3, victim: 1, open: 5, click: 2 },
        recent_events: [
          { event_type: 'submit', created_at: '2026-08-30 09:12:40' },
          { event_type: 'open', created_at: '2026-08-30 09:10:01' } ] } },
      errors: DETAIL_ERRORS,
    },
  ]},
  { id: 'template', name: '模板管理（scope: template）', children: [
    { id: 't1', name: '模板列表', method: 'GET', path: '/openapi/v1/templates',
      desc: '邮件模板列表（只读，不含正文），支持场景筛选',
      params: [AUTH_PARAM, { name: 'scene', type: 'string', required: false, default: '-', desc: 'finance/hr/system/holiday/prize/security' }],
      url_example: '/openapi/v1/templates?scene=finance',
      res_example: { code: 0, message: 'ok', data: { total: 2, list: [
        { id: 12, name: '薪酬调整通知模板', scene: 'finance', subject: '关于薪酬调整的通知',
          source: 'ai', status: 'approved', stars: 4, used_count: 3, click_rate: 22.5,
          created_at: '2026-08-20 14:00:00' } ] } },
      errors: GATEWAY_ERRORS,
    },
    { id: 't2', name: '模板详情', method: 'GET', path: '/openapi/v1/templates/{tid}',
      desc: '邮件模板详情（含 HTML 正文、模板变量与追踪开关）',
      params: [AUTH_PARAM, { name: 'tid', type: 'int', required: true, default: '-', desc: '模板ID（路径参数）' }],
      url_example: '/openapi/v1/templates/12',
      res_example: { code: 0, message: 'ok', data: {
        id: 12, name: '薪酬调整通知模板', scene: 'finance', subject: '关于薪酬调整的通知',
        html_body: '<p>您好 {{.Name}}：</p><p>请查收本季度薪酬调整通知。</p>',
        variables: ['{{.Name}}', '{{.ResetURL}}'], source: 'ai', status: 'approved', stars: 4,
        track_pixel: true, track_link: true, track_attach: false, created_at: '2026-08-20 14:00:00' } },
      errors: DETAIL_ERRORS,
    },
  ]},
  { id: 'incident', name: '举报管理（scope: mail_report）', children: [
    { id: 'i1', name: '举报列表', method: 'GET', path: '/openapi/v1/mail-reports',
      desc: '员工举报列表（只读），支持按分类筛选',
      params: [
        AUTH_PARAM,
        { name: 'classification', type: 'string', required: false, default: '-', desc: 'pending/drill/real_phishing/false_positive/spam' },
        { name: 'page', type: 'int', required: false, default: '1', desc: '页码' },
        { name: 'page_size', type: 'int', required: false, default: '20', desc: '每页数量（≤100）' },
      ],
      url_example: '/openapi/v1/mail-reports?classification=drill&page=1&page_size=20',
      res_example: { code: 0, message: 'ok', data: { total: 1, page: 1, page_size: 20, list: [
        { id: 9001, channel: 'outlook_plugin', subject: '可疑邮件：您的邮箱即将停用', from_addr: 'hr@corp.com',
          reporter_email: 'lisi@corp.com', classification: 'drill', classifier: 'auto',
          matched_campaign_id: 101, created_at: '2026-08-30 10:00:00', handled_at: null } ] } },
      errors: GATEWAY_ERRORS,
    },
  ]},
  { id: 'system', name: '系统管理（scope: system）', children: [
    { id: 's1', name: '平台基础信息', method: 'GET', path: '/openapi/v1/system/info',
      desc: '平台名称与数据规模概览（演练/员工/部门总数）',
      params: [AUTH_PARAM],
      url_example: '/openapi/v1/system/info',
      res_example: { code: 0, message: 'ok', data: { app_name: 'PhishLab', campaign_total: 36, emp_total: 1250, dept_total: 24 } },
      errors: GATEWAY_ERRORS,
    },
  ]},
]

const currentApi = ref<ApiNode | null>(apiTree[0].children![0])
function onApiClick(node: ApiNode) { if (node.method) currentApi.value = node }

function methodColor(m?: string) {
  return ({ GET: 'primary', POST: 'success', PUT: 'warning', DELETE: 'danger' } as any)[m || 'GET'] || 'info'
}

function copyJson(obj: any) {
  const text = JSON.stringify(obj, null, 2)
  navigator.clipboard?.writeText(text)
  ElMessage.success('已复制到剪贴板')
}

function copyText(text: string) {
  navigator.clipboard?.writeText(text)
  ElMessage.success('已复制到剪贴板')
}

const logMiniCards = computed(() => [
  { title: '总调用数', value: statsData.value ? `${statsData.value.total_calls.toLocaleString()} 次` : '—', accent: 'blue' as Accent },
  { title: '成功率', value: statsData.value ? `${statsData.value.success_rate.toFixed(2)} %` : '—', accent: 'green' as Accent },
  { title: '平均延迟', value: statsData.value ? `${statsData.value.avg_latency} ms` : '—', accent: 'orange' as Accent },
])
const logFilter = reactive({ app: '' as number | string, method: '', status: '', range: [] as any[], kw: '' })
const logs = ref<OpenApiLogItem[]>([])
const logTotal = ref(0)
const logPage = reactive({ page: 1, pageSize: 20 })

function logQuery() {
  const app = apps.value.find(a => a.id === logFilter.app)
  const [start, end] = logFilter.range || []
  return {
    app_id: app?.app_id || undefined,
    method: logFilter.method || undefined,
    status: logFilter.status || undefined,
    kw: logFilter.kw || undefined,
    start: start ? new Date(start).toISOString() : undefined,
    end: end ? new Date(end).toISOString() : undefined,
    page: logPage.page,
    pageSize: logPage.pageSize,
  }
}

async function loadLogs(p = 1) {
  logPage.page = p
  try {
    const data = await openapiApi.logs(logQuery())
    logs.value = data.list
    logTotal.value = data.total
  } catch {
    // 失败提示由 http 拦截器处理
  }
}

function onLogSize(size: number) {
  logPage.pageSize = size
  loadLogs(1)
}

const logDetailVisible = ref(false)
const logDetail = ref<any>(null)

function openLogDetail(row: any) {
  logDetail.value = {
    ...row,
    req_id: 'req-' + row.id,
    // 后端不记录请求/响应正文（敏感面控制），错误仅摘要
    error: row.error ? { code: String(row.status_code), message: row.error } : null,
  }
  logDetailVisible.value = true
}

onMounted(() => {
  loadApps()
  loadStats()
  loadLogs(1)
})

function methodTag(m: string) {
  return ({ GET: 'primary', POST: 'success', PUT: 'warning', DELETE: 'danger' } as any)[m] || 'info'
}
function statusTag(code: number) {
  if (code >= 200 && code < 300) return 'success'
  if (code >= 400 && code < 500) return 'warning'
  return 'danger'
}

function tableize(obj: any) {
  if (!obj) return []
  return Object.entries(obj).map(([key, val]) => ({ key, val }))
}
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.cat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  &.active, &:hover { background: rgba(13,148,136,0.1); }
}
.cat-icon { font-size: 16px; }
.cat-name { flex: 1; font-size: 13px; }

.app-avatar {
  width: 28px; height: 28px; border-radius: 6px;
  color: #fff; font-weight: 600; font-size: 13px;
  display: inline-flex; align-items: center; justify-content: center;
}

.docs-hint { margin-bottom: 12px; }
.docs-layout {
  display: flex;
  gap: 12px;
  min-height: 560px;
}
.docs-tree {
  width: 260px;
  flex-shrink: 0;
  background: var(--color-background-secondary);
  border-radius: 8px;
  padding: 8px;
  overflow: auto;
}
.docs-content { flex: 1; min-width: 0; }

.api-head { padding: 4px 2px 8px; }
.api-url {
  background: #2d333b; color: #e6edf3;
  padding: 4px 10px; border-radius: 4px;
  font-size: 12px; margin-left: 8px;
  word-break: break-all;
}
.api-name { margin: 12px 0 4px; font-size: 18px; }
.api-desc { margin: 0; font-size: 13px; color: var(--color-text-secondary); }

.json-block {
  background: #f6f8fa;
  padding: 12px;
  border-radius: 6px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
  max-height: 360px;
}
.nested-card { margin: 0; }

.log-mini-title { font-size: 12px; color: var(--color-text-secondary); }
.log-mini-value { font-size: 22px; font-weight: 600; margin-top: 4px; }

.scope-group {
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.scope-group-name {
  font-size: 12px; color: var(--color-text-secondary);
  font-weight: 500; margin-bottom: 6px;
}
.log-detail :deep(.el-descriptions__label) { width: 100px; }
</style>
