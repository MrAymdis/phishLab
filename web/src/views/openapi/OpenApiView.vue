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

          <el-table :data="apps" size="small" style="margin-top: 12px">
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
                <el-tag :type="row.status === 'enabled' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'enabled' ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="150" prop="created_at" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link size="small" type="primary">编辑密钥</el-button>
                <el-button link size="small" type="primary">权限编辑</el-button>
                <el-button link size="small" :type="row.status === 'enabled' ? 'warning' : 'success'" @click="toggleStatus(row)">
                  {{ row.status === 'enabled' ? '禁用' : '启用' }}
                </el-button>
                <el-button link size="small" type="danger">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination style="margin-top: 12px; justify-content: flex-end"
            layout="total, sizes, prev, pager, next" :total="36" :page-sizes="[10,20,50]" />
        </el-tab-pane>

        <el-tab-pane label="API文档" name="docs">
          <div class="docs-layout">
            <div class="docs-tree">
              <el-tree :data="apiTree" node-key="id" :props="{ label: 'name', children: 'children' }"
                :expand-on-click-node="false" :default-expanded-keys="['campaign']"
                :current-node-key="currentApi?.id" @node-click="onApiClick" />
            </div>
            <div class="docs-content" v-if="currentApi">
              <div class="api-head">
                <el-tag :type="methodColor(currentApi.method)" effect="dark" size="small">{{ currentApi.method }}</el-tag>
                <code class="api-url">{{ currentApi.path }}</code>
                <h3 class="api-name">{{ currentApi.name }}</h3>
                <p class="api-desc">{{ currentApi.desc }}</p>
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

              <div class="card card-green nested-card" style="margin-top: 12px">
                <div class="card-title">
                  请求体示例
                  <el-button size="small" link type="primary" @click="copyJson(currentApi.req_example)">复制</el-button>
                </div>
                <pre class="json-block">{{ JSON.stringify(currentApi.req_example, null, 2) }}</pre>
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
            <el-button size="small" type="primary">查询</el-button>
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
            layout="total, sizes, prev, pager, next" :total="586" :page-sizes="[10,20,50,100]" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="createAppVisible" title="创建应用" width="560px">
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
        <el-button type="primary" @click="submitApp">确认创建</el-button>
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
import { ref, reactive } from 'vue'
import type { EChartsOption } from 'echarts'
import { Plus, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import BaseChart from '@/components/base/BaseChart.vue'

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

const tab = ref<'overview' | 'apps' | 'docs' | 'logs'>('overview')

const overviewStats: { title: string; value: string; suffix: string; sub: string; accent: Accent }[] = [
  { title: '总调用数', value: '1,286,420', suffix: ' 次', sub: '↑ 18.2% 本周', accent: 'blue' },
  { title: '活跃应用数', value: '36', suffix: ' 个', sub: '新增 4 个本月', accent: 'teal' },
  { title: '调用成功率', value: '99.84', suffix: '%', sub: 'SLA 99.9% 达标', accent: 'green' },
  { title: '平均响应时间', value: '86', suffix: ' ms', sub: 'P99 412ms', accent: 'orange' },
]

const categories = [
  { key: 'campaign', name: '演练管理', icon: '🎯', count: 12, tagType: 'primary' as const },
  { key: 'user', name: '用户管理', icon: '👥', count: 8, tagType: 'success' as const },
  { key: 'template', name: '模板管理', icon: '📧', count: 10, tagType: 'warning' as const },
  { key: 'report', name: '数据报表', icon: '📊', count: 6, tagType: 'info' as const },
  { key: 'report', name: '举报管理', icon: '🛡️', count: 5, tagType: 'danger' as const },
  { key: 'system', name: '系统管理', icon: '⚙️', count: 7, tagType: 'info' as const },
]
const activeCat = ref('campaign')

const trendChart: EChartsOption = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['调用次数', '成功率%'], top: 0, textStyle: { fontSize: 11 } },
  grid: { left: 48, right: 52, top: 32, bottom: 28 },
  xAxis: { type: 'category', data: ['08-10', '08-11', '08-12', '08-13', '08-14', '08-15', '08-16'] },
  yAxis: [
    { type: 'value', name: '调用次数', axisLabel: { fontSize: 11 } },
    { type: 'value', name: '%', min: 95, max: 100, axisLabel: { fontSize: 11 } },
  ],
  series: [
    { name: '调用次数', type: 'bar', barWidth: 18, data: [168200, 175400, 182100, 171800, 196200, 201500, 191220],
      itemStyle: { color: '#378ADD', borderRadius: [4, 4, 0, 0] } },
    { name: '成功率%', type: 'line', yAxisIndex: 1, smooth: true,
      data: [99.72, 99.81, 99.78, 99.85, 99.91, 99.88, 99.84],
      itemStyle: { color: '#1d9e75' }, lineStyle: { width: 2 },
      areaStyle: { color: 'rgba(29,158,117,0.12)' } },
  ],
}

const appKw = ref('')
const apps = ref(([
  { id: 1, name: '内部OA系统', app_id: 'app_0a1b2c3d', secret: 'sk_live_8f3e2a9d7b1c5e8f', calls: 428600, status: 'enabled', created_at: '2026-04-12 10:21',
    scopes: ['campaign:read', 'campaign:write', 'user:read', 'report:read'], color: '#378ADD', _show: false },
  { id: 2, name: 'HR招聘平台', app_id: 'app_9z8y7x6w', secret: 'sk_live_2d6c8f4a0e1b9c3d', calls: 152400, status: 'enabled', created_at: '2026-05-03 14:56',
    scopes: ['user:read', 'user:write', 'template:read'], color: '#7f77dd', _show: false },
  { id: 3, name: '数据中台BI', app_id: 'app_e5r6t7y8', secret: 'sk_live_5a9b3c7e2f8d1a4b', calls: 286500, status: 'enabled', created_at: '2026-03-20 09:12',
    scopes: ['report:read', 'campaign:read', 'user:read'], color: '#1d9e75', _show: false },
  { id: 4, name: '财务对接系统', app_id: 'app_u1i2o3p4', secret: 'sk_live_1c3e5b7d9a2f4c8e', calls: 102800, status: 'disabled', created_at: '2026-06-11 16:40',
    scopes: ['user:read', 'campaign:read'], color: '#d85a30', _show: false },
  { id: 5, name: 'SOC安全运营', app_id: 'app_q0w9e8r7', secret: 'sk_live_9f2b6d8a1c4e7a3f', calls: 198700, status: 'enabled', created_at: '2026-02-28 11:05',
    scopes: ['campaign:read', 'campaign:write', 'report:read', 'report:write', 'user:read', 'incident:write'], color: '#a32d2d', _show: false },
]).map(a => reactive(a)))

function regenSecret(row: any) {
  ElMessage.success('AppSecret 已重新生成')
  row.secret = 'sk_live_' + Math.random().toString(36).slice(2, 18)
}
function toggleStatus(row: any) {
  row.status = row.status === 'enabled' ? 'disabled' : 'enabled'
  ElMessage.success(`应用已${row.status === 'enabled' ? '启用' : '禁用'}`)
}

const createAppVisible = ref(false)
const newApp = reactive({ name: '', desc: '', scopes: [] as string[], ip_whitelist: '', callback_url: '', rate_limit: 1000 })
const scopeGroups = [
  { name: '演练管理', items: ['campaign:read', 'campaign:write', 'campaign:delete'] },
  { name: '用户管理', items: ['user:read', 'user:write', 'user:delete'] },
  { name: '模板管理', items: ['template:read', 'template:write'] },
  { name: '数据报表', items: ['report:read', 'report:write'] },
]
function submitApp() {
  if (!newApp.name) return ElMessage.warning('请填写应用名称')
  ElMessage.success('应用已创建，AppID/Secret 请妥善保管')
  createAppVisible.value = false
}

interface ApiNode {
  id: string; name: string; method?: Method; path?: string; desc?: string;
  children?: ApiNode[]; params?: any[]; req_example?: any; res_example?: any; errors?: any[];
}
const apiTree: ApiNode[] = [
  { id: 'campaign', name: '演练管理', children: [
    { id: 'c1', name: '获取演练列表', method: 'GET', path: '/api/v1/campaigns', desc: '分页获取演练活动列表，支持按状态、类型、关键字筛选',
      params: [
        { name: 'page', type: 'int', required: false, default: '1', desc: '页码' },
        { name: 'page_size', type: 'int', required: false, default: '20', desc: '每页数量' },
        { name: 'status', type: 'string', required: false, default: '-', desc: 'running/scheduled/completed' },
        { name: 'keyword', type: 'string', required: false, default: '-', desc: '按名称搜索' },
      ],
      req_example: {},
      res_example: { code: 0, message: 'ok', data: { total: 128, items: [{ id: 1, name: 'Q3全员演练', status: 'running' }] } },
      errors: [{ code: 'E4001', message: '参数格式错误', http: '400' }, { code: 'E5000', message: '服务内部错误', http: '500' }],
    },
    { id: 'c2', name: '创建演练', method: 'POST', path: '/api/v1/campaigns', desc: '创建新的钓鱼演练活动',
      params: [{ name: 'name', type: 'string', required: true, default: '-', desc: '演练名称' }],
      req_example: { name: 'Q3全员防钓鱼演练', type: 'mail', target_count: 3580 },
      res_example: { code: 0, data: { id: 101, status: 'scheduled' } },
      errors: [{ code: 'E4002', message: '名称不能为空', http: '400' }],
    },
    { id: 'c3', name: '更新演练', method: 'PUT', path: '/api/v1/campaigns/{id}', desc: '更新指定演练配置',
      params: [{ name: 'id', type: 'int', required: true, default: '-', desc: '演练ID(路径参数)' }],
      req_example: { description: '更新描述' },
      res_example: { code: 0, message: 'updated' },
      errors: [{ code: 'E4041', message: '演练不存在', http: '404' }],
    },
    { id: 'c4', name: '删除演练', method: 'DELETE', path: '/api/v1/campaigns/{id}', desc: '删除指定演练（仅草稿状态可删）',
      params: [{ name: 'id', type: 'int', required: true, default: '-', desc: '演练ID' }],
      req_example: {},
      res_example: { code: 0 },
      errors: [{ code: 'E4031', message: '仅草稿状态可删除', http: '403' }],
    },
  ]},
  { id: 'user', name: '用户管理', children: [
    { id: 'u1', name: '获取用户列表', method: 'GET', path: '/api/v1/users', desc: '获取组织内用户',
      params: [{ name: 'dept', type: 'string', required: false, default: '-', desc: '部门筛选' }],
      req_example: {},
      res_example: { code: 0, data: { total: 3580, items: [] } },
      errors: [{ code: 'E5000', message: '服务内部错误', http: '500' }],
    },
    { id: 'u2', name: '批量导入用户', method: 'POST', path: '/api/v1/users/bulk', desc: '通过CSV批量导入用户',
      params: [], req_example: { file: '[binary]' }, res_example: { code: 0, data: { success: 200, failed: 2 } }, errors: [],
    },
  ]},
  { id: 'template', name: '模板管理', children: [
    { id: 't1', name: '获取模板列表', method: 'GET', path: '/api/v1/templates', desc: '获取钓鱼邮件/短信模板列表',
      params: [], req_example: {}, res_example: { code: 0, data: { total: 46, items: [] } }, errors: [],
    },
  ]},
  { id: 'report', name: '数据报表', children: [
    { id: 'r1', name: '演练报表导出', method: 'POST', path: '/api/v1/reports/campaign/{id}', desc: '导出指定演练的Excel/PDF报表',
      params: [], req_example: { format: 'pdf' }, res_example: { code: 0, data: { url: '/download/x.pdf' } }, errors: [],
    },
  ]},
  { id: 'incident', name: '举报管理', children: [
    { id: 'i1', name: '举报事件列表', method: 'GET', path: '/api/v1/incidents', desc: '获取员工举报事件列表',
      params: [], req_example: {}, res_example: { code: 0 }, errors: [],
    },
  ]},
  { id: 'system', name: '系统管理', children: [
    { id: 's1', name: '健康检查', method: 'GET', path: '/api/v1/system/health', desc: '检测API服务健康状态',
      params: [], req_example: {}, res_example: { code: 0, status: 'healthy' }, errors: [],
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

const logMiniCards = [
  { title: '今日调用', value: '191,220 次', accent: 'blue' as Accent },
  { title: '成功率', value: '99.91 %', accent: 'green' as Accent },
  { title: '平均延迟', value: '82 ms', accent: 'orange' as Accent },
]
const logFilter = reactive({ app: '', method: '', status: '', range: [] as any[], kw: '' })
const logs = [
  { time: '2026-08-16 14:38:02', app_name: 'SOC安全运营', method: 'GET', path: '/api/v1/campaigns?page=1&status=running', status_code: 200, response_ms: 62, ip: '10.12.34.56',
    req_id: 'req-abc123', req_headers: { 'Authorization': 'Bearer sk_***', 'User-Agent': 'SOC-Bot/1.0', 'X-Forwarded-For': '10.12.34.56' },
    req_body: {}, res_headers: { 'Content-Type': 'application/json', 'X-RateLimit-Remaining': '988' },
    res_body: { code: 0, data: { total: 3, items: [{ id: 1 }, { id: 2 }, { id: 3 }] } } },
  { time: '2026-08-16 14:37:48', app_name: 'HR招聘平台', method: 'POST', path: '/api/v1/users/bulk', status_code: 200, response_ms: 840, ip: '10.12.34.78',
    req_id: 'req-def456', req_headers: { 'Authorization': 'Bearer sk_***' }, req_body: { file: '[binary csv 200 rows]' },
    res_headers: { 'Content-Type': 'application/json' }, res_body: { code: 0, data: { success: 198, failed: 2 } } },
  { time: '2026-08-16 14:37:12', app_name: '内部OA系统', method: 'PUT', path: '/api/v1/campaigns/12', status_code: 404, response_ms: 28, ip: '10.12.34.11',
    req_id: 'req-ghi789', req_headers: {}, req_body: { name: 'test' },
    res_headers: {}, res_body: { code: 'E4041', message: '演练不存在' }, error: { code: 'E4041', message: '资源不存在' } },
  { time: '2026-08-16 14:36:55', app_name: '数据中台BI', method: 'GET', path: '/api/v1/reports/campaign/1/summary', status_code: 500, response_ms: 1240, ip: '10.12.34.201',
    req_id: 'req-jkl012', req_headers: {}, req_body: {},
    res_headers: {}, res_body: { code: 'E5000', message: '数据库连接超时' }, error: { code: 'E5000', message: '服务内部错误: connection timeout' } },
  { time: '2026-08-16 14:36:20', app_name: '内部OA系统', method: 'DELETE', path: '/api/v1/campaigns/88', status_code: 403, response_ms: 18, ip: '10.12.34.11',
    req_id: 'req-mno345', req_headers: {}, req_body: {},
    res_headers: {}, res_body: { code: 'E4031', message: '仅草稿状态可删除' }, error: { code: 'E4031', message: '禁止删除' } },
  { time: '2026-08-16 14:35:48', app_name: 'SOC安全运营', method: 'POST', path: '/api/v1/campaigns', status_code: 200, response_ms: 156, ip: '10.12.34.56',
    req_id: 'req-pqr678', req_headers: {}, req_body: { name: '测试演练', type: 'mail' },
    res_headers: {}, res_body: { code: 0, data: { id: 201 } } },
]

const logDetailVisible = ref(false)
const logDetail = ref<any>(null)

function openLogDetail(row: any) {
  logDetail.value = row
  logDetailVisible.value = true
}

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
