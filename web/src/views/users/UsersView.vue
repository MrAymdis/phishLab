<template>
  <div class="page-container">
    <PageHeader title="用户和组">
      <template #actions>
        <el-button :icon="Upload" @click="onImportCsv">导入CSV</el-button>
        <el-button :icon="Download" @click="onExportCsv">批量导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openEmpDialog()">添加员工</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="12" class="users-row">
      <!-- ============ 左侧：部门树 ============ -->
      <el-col :span="5">
        <div class="card card-blue dept-card">
          <div class="card-title">
            <span class="card-title-text">
              <el-icon class="title-icon"><OfficeBuilding /></el-icon>
              组织架构
            </span>
          </div>
          <el-input
            v-model="deptKw"
            size="small"
            placeholder="搜索部门..."
            :prefix-icon="Search"
            clearable
            class="dept-search"
          />
          <el-tree
            ref="deptTreeRef"
            :data="deptTree"
            node-key="id"
            :props="treeProps"
            :filter-node-method="filterDeptNode"
            default-expand-all
            highlight-current
            class="dept-tree"
            @node-click="onDeptClick"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <span class="tree-label">{{ node.label }}</span>
                <span class="tree-count">{{ data.count }}</span>
              </span>
            </template>
          </el-tree>
          <div class="dept-actions">
            <el-button size="small" class="dept-btn" :icon="Refresh" @click="onSyncAd">
              同步AD/LDAP
            </el-button>
            <el-button size="small" class="dept-btn" :icon="Plus">添加部门</el-button>
          </div>
        </div>
      </el-col>

      <!-- ============ 中间：统计 + 工具栏 + 表格 ============ -->
      <el-col :span="13">
        <!-- 统计卡片 -->
        <el-row :gutter="12" class="stat-row">
          <el-col :span="6">
            <StatCard title="总人数" value="3,580" accent="blue" sub="覆盖 8 个部门" />
          </el-col>
          <el-col :span="6">
            <StatCard title="本月新增" :value="42" accent="green" value-color="#1D9E75" sub="↑ 较上月 +18%" />
          </el-col>
          <el-col :span="6">
            <StatCard title="高风险人员" :value="86" accent="red" value-color="#A32D2D" sub="需优先培训" />
          </el-col>
          <el-col :span="6">
            <StatCard title="已培训完成" value="2,940" accent="teal" value-color="#0D9488" sub="完成率 82.1%" />
          </el-col>
        </el-row>

        <!-- 工具栏 -->
        <div class="card toolbar-card">
          <div class="toolbar">
            <span class="filter-label">标签：</span>
            <el-radio-group v-model="tagFilter" size="small">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button v-for="t in tagOptions" :key="t" :value="t">{{ t }}</el-radio-button>
            </el-radio-group>
            <el-button size="small" text type="primary" @click="openTagDialog" class="tag-add-btn">+ 新建标签</el-button>
            <el-divider direction="vertical" />
            <span class="filter-label">风险：</span>
            <el-radio-group v-model="riskFilter" size="small">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="high">高</el-radio-button>
              <el-radio-button value="mid">中</el-radio-button>
              <el-radio-button value="low">低</el-radio-button>
            </el-radio-group>
            <div class="toolbar-right">
              <el-input
                v-model="empKw"
                size="small"
                placeholder="搜索姓名/工号/邮箱..."
                :prefix-icon="Search"
                clearable
                class="emp-search"
              />
              <el-button :icon="Upload" size="small" @click="onImportCsv">导入CSV</el-button>
              <el-button type="primary" :icon="Plus" size="small" @click="openEmpDialog()">添加员工</el-button>
            </div>
          </div>
        </div>

        <!-- 员工列表 -->
        <div class="card table-card">
          <div class="table-header">
            <span class="selected-info">共 {{ filteredEmployees.length }} 条</span>
            <div class="page-size-wrap">
              <span class="page-size-label">每页</span>
              <el-select v-model="empPageSize" size="small" class="page-size-select">
                <el-option :value="10" label="10" />
                <el-option :value="20" label="20" />
                <el-option :value="50" label="50" />
              </el-select>
              <span class="page-size-label">条</span>
            </div>
          </div>
          <el-table :data="pagedEmployees" size="small" class="emp-table" @row-click="selectEmp">
            <el-table-column label="员工" min-width="160">
              <template #default="{ row }: { row: Employee }">
                <div class="emp-cell">
                  <span class="emp-avatar-sm" :style="{ background: row.avatarColor }">{{ row.name.charAt(0) }}</span>
                  <div class="emp-info">
                    <div class="emp-name">{{ row.name }}</div>
                    <div class="emp-no">{{ row.no }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="deptShort" label="部门" width="100" />
            <el-table-column prop="pos" label="岗位" width="130" />
            <el-table-column prop="email" label="邮箱" min-width="180" />
            <el-table-column prop="phone" label="手机号" width="120" />
            <el-table-column label="风险等级" width="110" align="center">
              <template #default="{ row }: { row: Employee }">
                <span class="badge" :style="riskBadgeStyle(row.risk)">{{ riskMap[row.risk].label }}</span>
                <span class="risk-score" :style="{ color: riskMap[row.risk].color }">{{ row.riskScore }}</span>
              </template>
            </el-table-column>
            <el-table-column label="中招次数" width="90" align="center">
              <template #default="{ row }: { row: Employee }">
                <span :class="['clicks', row.clicks > 0 ? 'clicks-danger' : '']">{{ row.clicks }}</span>
              </template>
            </el-table-column>
            <el-table-column label="培训状态" width="100" align="center">
              <template #default="{ row }: { row: Employee }">
                <span class="badge" :style="trainingBadgeStyle(row.training)">{{ trainingMap[row.training].label }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }: { row: Employee }">
                <el-button size="small" link type="primary" @click.stop="selectEmp(row)">查看档案</el-button>
                <el-button size="small" link @click.stop="openEmpDialog(row)">编辑</el-button>
                <el-button size="small" link type="success" @click.stop="onSendDrill(row)">发送演练</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer">
            <span class="page-info">{{ pageInfo }}</span>
            <el-pagination
              layout="prev, pager, next"
              v-model:current-page="empPage"
              :page-size="empPageSize"
              :total="filteredEmployees.length"
              small
            />
          </div>
        </div>
      </el-col>

      <!-- ============ 右侧：员工风险画像 ============ -->
      <el-col :span="6">
        <div v-if="selectedEmp" class="right-panel">
          <!-- 基本信息 -->
          <div class="card card-blue profile-head-card">
            <div class="profile-head">
              <span class="emp-avatar-lg" :style="{ background: selectedEmp.avatarColor }">{{ selectedEmp.name.charAt(0) }}</span>
              <div class="profile-head-info">
                <div class="profile-name-row">
                  <span class="profile-name">{{ selectedEmp.name }}</span>
                  <span class="badge" :style="riskBadgeStyle(selectedEmp.risk)">{{ riskMap[selectedEmp.risk].text }}</span>
                </div>
                <div class="profile-meta-row">
                  <span>工号：<span class="mono">{{ selectedEmp.no }}</span></span>
                  <span>部门：<span>{{ selectedEmp.dept }}</span></span>
                </div>
                <div class="profile-meta-row">
                  <span>岗位：<span>{{ selectedEmp.pos }}</span></span>
                </div>
                <div class="profile-meta-row">
                  <span>邮箱：<span class="mono">{{ selectedEmp.email }}</span></span>
                  <span>手机：<span class="mono">{{ selectedEmp.phone }}</span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- 风险画像5维条状图 -->
          <div class="card card-red">
            <div class="card-title">
              <span class="card-title-text">风险画像</span>
              <span class="card-title-extra">
                综合评分
                <span class="risk-total" :style="{ color: riskMap[selectedEmp.risk].color }">{{ selectedEmp.riskScore }}</span>
                /100
              </span>
            </div>
            <div v-for="d in selectedRiskDims" :key="d.label" class="risk-dim">
              <span class="risk-dim-label">{{ d.label }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${d.val}%`, background: d.color }"></div>
              </div>
              <span class="risk-dim-value" :style="{ color: d.color }">{{ d.val }}</span>
            </div>
          </div>

          <!-- 培训完成度 -->
          <div class="card card-teal">
            <div class="card-title">
              <span class="card-title-text">培训完成度</span>
              <span class="card-title-extra">{{ trainingPct }}</span>
            </div>
            <div class="training-status-wrap">
              <div class="training-status" :style="{ color: trainingMap[selectedEmp.training].color }">
                {{ trainingMap[selectedEmp.training].label }}
              </div>
              <div class="training-sub">本年度安全培训计划</div>
            </div>
            <div class="course-list">
              <div v-for="c in selectedCourses" :key="c.name" class="course-item">
                <el-icon :color="c.done ? '#1D9E75' : '#8c8c8c'">
                  <CircleCheckFilled v-if="c.done" />
                  <WarningFilled v-else />
                </el-icon>
                <span :class="['course-name', c.done ? '' : 'course-pending']">{{ c.name }}</span>
              </div>
            </div>
          </div>

          <!-- 历史演练行为轨迹 -->
          <div class="card card-orange">
            <div class="card-title">
              <span class="card-title-text">历史演练行为轨迹</span>
              <span class="card-title-extra">
                历史中招 <span class="num-danger">{{ selectedEmp.clicks }}</span> 次 · 举报
                <span class="num-success">{{ selectedReportCount }}</span> 次
              </span>
            </div>
            <el-timeline class="behavior-timeline">
              <el-timeline-item
                v-for="(ev, idx) in selectedTimeline"
                :key="idx"
                :timestamp="ev.time"
                :type="ev.type"
                placement="top"
              >
                <div class="ev-title">{{ ev.title }}</div>
                <div class="ev-desc">{{ ev.desc }}</div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </div>
        <div v-else class="card empty-card">
          <el-empty description="点击员工行查看风险画像" />
        </div>
      </el-col>
    </el-row>

    <!-- ============ 添加/编辑员工弹窗 ============ -->
    <el-dialog v-model="empDialogVisible" :title="empForm.id ? '编辑员工' : '添加员工'" width="640px" destroy-on-close>
      <el-form :model="empForm" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="姓名" required>
              <el-input v-model="empForm.name" placeholder="请输入员工姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工号" required>
              <el-input v-model="empForm.no" placeholder="如 EMP015" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="邮箱" required>
              <el-input v-model="empForm.email" placeholder="name@jianfa.com" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="empForm.phone" placeholder="138****0000" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="部门" required>
              <el-select v-model="empForm.dept" style="width: 100%">
                <el-option label="技术部 / 研发组" value="技术部 / 研发组" />
                <el-option label="技术部 / 运维组" value="技术部 / 运维组" />
                <el-option label="技术部 / 安全组" value="技术部 / 安全组" />
                <el-option label="财务部 / 会计组" value="财务部 / 会计组" />
                <el-option label="财务部 / 出纳组" value="财务部 / 出纳组" />
                <el-option label="人力资源部" value="人力资源部" />
                <el-option label="市场部" value="市场部" />
                <el-option label="行政部" value="行政部" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="岗位">
              <el-input v-model="empForm.pos" placeholder="如：研发工程师" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签">
          <div class="tag-chips">
            <span
              v-for="t in tagOptions"
              :key="t"
              :class="['tag-chip', empForm.tags.includes(t) ? 'selected' : '']"
              :style="empForm.tags.includes(t) ? { background: tagColorMap[t] || '#378ADD', borderColor: tagColorMap[t] || '#378ADD', color: '#fff' } : {}"
              @click="toggleEmpTag(t)"
            >{{ t }}</span>
            <span v-if="!inlineTagInputVisible" class="tag-chip tag-chip-add" @click="inlineTagInputVisible = true">+ 添加</span>
            <el-input
              v-else
              v-model="inlineTagName"
              size="small"
              class="tag-inline-input"
              placeholder="输入标签名回车确认"
              @keyup.enter="createInlineTag"
              @blur="createInlineTag"
            />
          </div>
        </el-form-item>
        <el-form-item label="初始风险值">
          <div class="risk-slider-wrap">
            <el-slider v-model="empForm.riskScore" :min="0" :max="100" style="flex: 1" />
            <span class="badge" :style="riskSliderBadgeStyle(empForm.riskScore)">{{ empForm.riskScore }}</span>
          </div>
          <div class="form-hint">0-30 低风险 · 31-70 中风险 · 71-100 高风险</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="empDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEmp">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建标签对话框 -->
    <el-dialog v-model="tagDialogVisible" title="新建标签" width="400px" :close-on-click-modal="false">
      <el-form :model="{ name: newTagName, color: newTagColor }" label-width="80px">
        <el-form-item label="标签名称">
          <el-input v-model="newTagName" placeholder="例如：实习生、部门负责人" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item label="标签颜色">
          <div class="color-picker-row">
            <div
              v-for="c in ['#378ADD', '#0D9488', '#E6A23C', '#F56C6C', '#67C23A', '#A05B8C', '#909399', '#409EFF']"
              :key="c"
              :class="['color-dot', { selected: newTagColor === c }]"
              :style="{ background: c }"
              @click="newTagColor = c"
            >
              <svg v-if="newTagColor === c" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
          </div>
          <div class="form-hint">选择标签在列表中的高亮颜色</div>
        </el-form-item>
        <el-form-item label="预览效果">
          <span class="tag-chip selected" :style="{ background: newTagColor, borderColor: newTagColor, color: '#fff' }">
            {{ newTagName || '标签预览' }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tagDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createTag">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElTree } from 'element-plus'
import {
  Upload, Download, Plus, Search, Refresh, OfficeBuilding,
  CircleCheckFilled, WarningFilled,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import { orgApi } from '@/api'

// ============ 类型定义 ============
type RiskLevel = 'high' | 'mid' | 'low'
type TrainingStatus = 'completed' | 'progress' | 'none'

interface Employee {
  id: number
  name: string
  no: string
  dept: string
  deptShort: string
  pos: string
  email: string
  phone: string
  risk: RiskLevel
  riskScore: number
  tags: string[]
  clicks: number
  training: TrainingStatus
  avatarColor: string
}

interface DeptNode {
  id: number
  label: string
  count: number
  children?: DeptNode[]
}

interface RiskDim {
  label: string
  val: number
  color: string
}

interface TimelineEvent {
  time: string
  type: 'primary' | 'success' | 'warning' | 'danger'
  title: string
  desc: string
}

// ============ 风险/培训映射 ============
const riskMap: Record<RiskLevel, { label: string; text: string; color: string; bg: string }> = {
  high: { label: '高', text: '高风险', color: '#D85A30', bg: 'rgba(216,90,48,0.15)' },
  mid: { label: '中', text: '中风险', color: '#EF9F27', bg: 'rgba(239,159,39,0.15)' },
  low: { label: '低', text: '低风险', color: '#1D9E75', bg: 'rgba(29,158,117,0.15)' },
}

const trainingMap: Record<TrainingStatus, { label: string; color: string; bg: string }> = {
  completed: { label: '已完成', color: '#1D9E75', bg: 'rgba(29,158,117,0.15)' },
  progress: { label: '进行中', color: '#378ADD', bg: 'rgba(55,138,221,0.15)' },
  none: { label: '未开始', color: '#6b7280', bg: 'rgba(107,114,128,0.15)' },
}

const avatarColors = ['#378ADD', '#1D9E75', '#7F77DD', '#EF9F27', '#D85A30', '#0D9488']

function riskBadgeStyle(risk: RiskLevel) {
  const m = riskMap[risk]
  return { background: m.bg, color: m.color }
}
function trainingBadgeStyle(s: TrainingStatus) {
  const m = trainingMap[s]
  return { background: m.bg, color: m.color }
}
function riskSliderBadgeStyle(v: number) {
  if (v <= 30) return { background: 'rgba(29,158,117,0.15)', color: '#1D9E75' }
  if (v <= 70) return { background: 'rgba(239,159,39,0.15)', color: '#EF9F27' }
  return { background: 'rgba(216,90,48,0.15)', color: '#D85A30' }
}

// ============ 部门树 ============
const treeProps = { label: 'label', children: 'children' }

const deptTree = ref<DeptNode[]>([
  {
    id: 0, label: '总公司', count: 3580,
    children: [
      {
        id: 1, label: '技术部', count: 420,
        children: [
          { id: 11, label: '研发组', count: 186 },
          { id: 12, label: '运维组', count: 128 },
          { id: 13, label: '安全组', count: 106 },
        ],
      },
      {
        id: 2, label: '财务部', count: 56,
        children: [
          { id: 21, label: '会计组', count: 32 },
          { id: 22, label: '出纳组', count: 24 },
        ],
      },
      { id: 3, label: '人力资源部', count: 86 },
      { id: 4, label: '市场部', count: 320 },
      { id: 5, label: '行政部', count: 48 },
    ],
  },
])

const deptKw = ref('')
const deptTreeRef = ref<InstanceType<typeof ElTree>>()
const selectedDept = ref<DeptNode | null>(null)

watch(deptKw, (val) => {
  deptTreeRef.value?.filter(val)
})

// el-tree 过滤函数：data 类型按 el-tree FilterNodeMethodFunction 期望放宽，避免 any
function filterDeptNode(value: string, data: Record<string, unknown>): boolean {
  if (!value) return true
  const label = data.label
  return typeof label === 'string' && label.includes(value)
}

function collectDeptLabels(node: DeptNode): string[] {
  return [node.label, ...(node.children ?? []).flatMap(c => collectDeptLabels(c))]
}

function onDeptClick(data: DeptNode) {
  selectedDept.value = data
  loadUsers(data.id === 0 ? undefined : data.id)
  if (data.label === '总公司') {
    ElMessage.info('已切换到「全部部门」')
  } else {
    ElMessage.info(`已筛选部门：${data.label}`)
  }
}

// ============ 接口加载（失败时保留演示数据） ============
async function loadDepts() {
  try {
    const tree = (await orgApi.deptTree()) as DeptNode[]
    if (Array.isArray(tree) && tree.length) deptTree.value = tree
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

async function loadUsers(deptId?: number) {
  try {
    const q: Record<string, unknown> = { page: 1, pageSize: 100 }
    if (deptId) q.dept_id = deptId
    const res = (await orgApi.users(q)) as { list: Employee[] }
    if (Array.isArray(res.list) && res.list.length) employeeRows.value = res.list
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

onMounted(() => {
  loadDepts()
  loadUsers()
})

// 选中部门时，允许命中所选节点或其任一子部门（含父部门名称命中员工 dept 字段）
const allowedDeptLabels = computed<Set<string> | null>(() => {
  if (!selectedDept.value || selectedDept.value.label === '总公司') return null
  return new Set(collectDeptLabels(selectedDept.value).filter(l => l !== '总公司'))
})

// ============ 员工数据（对齐 demo 14 条 mock，接口加载成功后覆盖） ============
const employeeRows = ref<Employee[]>([
  { id: 1, name: '张伟', no: 'EMP001', dept: '技术部 / 研发组', deptShort: '研发组', pos: '高级研发工程师', email: 'zhangwei@jianfa.com', phone: '138****2856', risk: 'high', riskScore: 82, tags: ['研发'], clicks: 3, training: 'completed', avatarColor: avatarColors[0] },
  { id: 2, name: '李娜', no: 'EMP002', dept: '财务部 / 会计组', deptShort: '会计组', pos: '会计主管', email: 'lina@jianfa.com', phone: '139****1024', risk: 'high', riskScore: 78, tags: ['财务'], clicks: 4, training: 'completed', avatarColor: avatarColors[1] },
  { id: 3, name: '王强', no: 'EMP003', dept: '技术部 / 运维组', deptShort: '运维组', pos: '运维工程师', email: 'wangqiang@jianfa.com', phone: '137****8832', risk: 'mid', riskScore: 55, tags: ['运维'], clicks: 1, training: 'progress', avatarColor: avatarColors[2] },
  { id: 4, name: '刘洋', no: 'EMP004', dept: '技术部 / 研发组', deptShort: '研发组', pos: '前端工程师', email: 'liuyang@jianfa.com', phone: '135****6677', risk: 'low', riskScore: 22, tags: ['研发'], clicks: 0, training: 'completed', avatarColor: avatarColors[3] },
  { id: 5, name: '陈静', no: 'EMP005', dept: '人力资源部', deptShort: '人力部', pos: 'HR专员', email: 'chenjing@jianfa.com', phone: '136****4458', risk: 'mid', riskScore: 48, tags: ['新员工'], clicks: 2, training: 'progress', avatarColor: avatarColors[4] },
  { id: 6, name: '赵磊', no: 'EMP006', dept: '技术部 / 安全组', deptShort: '安全组', pos: '安全工程师', email: 'zhaolei@jianfa.com', phone: '138****9912', risk: 'low', riskScore: 15, tags: ['运维'], clicks: 0, training: 'completed', avatarColor: avatarColors[5] },
  { id: 7, name: '孙芳', no: 'EMP007', dept: '市场部', deptShort: '市场部', pos: '市场经理', email: 'sunfang@jianfa.com', phone: '139****3344', risk: 'high', riskScore: 75, tags: [], clicks: 3, training: 'none', avatarColor: avatarColors[0] },
  { id: 8, name: '周明', no: 'EMP008', dept: '行政部', deptShort: '行政部', pos: '行政主管', email: 'zhouming@jianfa.com', phone: '133****7766', risk: 'mid', riskScore: 52, tags: [], clicks: 1, training: 'completed', avatarColor: avatarColors[1] },
  { id: 9, name: '吴婷', no: 'EMP009', dept: '财务部 / 出纳组', deptShort: '出纳组', pos: '出纳', email: 'wuting@jianfa.com', phone: '136****2200', risk: 'high', riskScore: 88, tags: ['财务'], clicks: 5, training: 'progress', avatarColor: avatarColors[2] },
  { id: 10, name: '郑浩', no: 'EMP010', dept: '技术部 / 研发组', deptShort: '研发组', pos: '架构师', email: 'zhenghao@jianfa.com', phone: '135****1188', risk: 'low', riskScore: 18, tags: ['研发'], clicks: 0, training: 'completed', avatarColor: avatarColors[3] },
  { id: 11, name: '黄丽', no: 'EMP011', dept: '人力资源部', deptShort: '人力部', pos: 'HRBP', email: 'huangli@jianfa.com', phone: '138****5599', risk: 'mid', riskScore: 50, tags: [], clicks: 1, training: 'completed', avatarColor: avatarColors[4] },
  { id: 12, name: '林峰', no: 'EMP012', dept: '市场部', deptShort: '市场部', pos: '品牌专员', email: 'linfeng@jianfa.com', phone: '139****6611', risk: 'mid', riskScore: 58, tags: ['新员工'], clicks: 2, training: 'none', avatarColor: avatarColors[5] },
  { id: 13, name: '徐敏', no: 'EMP013', dept: '财务部', deptShort: '财务部', pos: '财务总监', email: 'xumin@jianfa.com', phone: '137****0099', risk: 'high', riskScore: 72, tags: ['高管'], clicks: 3, training: 'completed', avatarColor: avatarColors[0] },
  { id: 14, name: '杨帆', no: 'EMP014', dept: '技术部', deptShort: '技术部', pos: 'CTO', email: 'yangfan@jianfa.com', phone: '135****0001', risk: 'low', riskScore: 12, tags: ['高管', '研发'], clicks: 0, training: 'completed', avatarColor: avatarColors[1] },
])

const tagOptions = ref<string[]>(['高管', '研发', '运维', '财务', '新员工'])
const tagColorMap: Record<string, string> = {
  高管: '#E6A23C', 研发: '#378ADD', 运维: '#0D9488', 财务: '#A05B8C', 新员工: '#67C23A',
}
const tagDialogVisible = ref(false)
const newTagName = ref('')
const newTagColor = ref('#378ADD')
const inlineTagInputVisible = ref(false)
const inlineTagName = ref('')

// ============ 筛选：部门 + 标签 + 风险 + 关键词 ============
const tagFilter = ref<string>('all')
const riskFilter = ref<'all' | RiskLevel>('all')
const empKw = ref('')
const empPage = ref(1)
const empPageSize = ref(20)

const filteredEmployees = computed(() => {
  const kw = empKw.value.trim().toLowerCase()
  const labels = allowedDeptLabels.value
  return employeeRows.value.filter(row => {
    // 部门树筛选：员工 deptShort 或 dept 命中任一选中节点（含子部门）
    if (labels) {
      const hit = labels.has(row.deptShort) || labels.has(row.dept) ||
        Array.from(labels).some(l => row.dept.includes(l))
      if (!hit) return false
    }
    if (tagFilter.value !== 'all' && !row.tags.includes(tagFilter.value)) return false
    if (riskFilter.value !== 'all' && row.risk !== riskFilter.value) return false
    if (kw) {
      const blob = (row.name + row.no + row.email + row.pos).toLowerCase()
      if (!blob.includes(kw)) return false
    }
    return true
  })
})

const pagedEmployees = computed(() =>
  filteredEmployees.value.slice(
    (empPage.value - 1) * empPageSize.value,
    empPage.value * empPageSize.value,
  ),
)

const pageInfo = computed(() => {
  const total = filteredEmployees.value.length
  if (total === 0) return '暂无记录'
  const start = (empPage.value - 1) * empPageSize.value + 1
  const end = Math.min(empPage.value * empPageSize.value, total)
  return `显示 ${start} - ${end} 条，共 ${total} 条记录`
})

watch([tagFilter, riskFilter, empKw, selectedDept], () => {
  empPage.value = 1
})

// ============ 选中员工（右侧风险画像联动） ============
// TODO: 可接入 orgApi.riskProfile(row.id) 用后端五维画像替换下方派生计算
const selectedEmp = ref<Employee | null>(employeeRows.value[0])

function selectEmp(row: Employee) {
  selectedEmp.value = row
}

// 风险画像 5 维：邮件识别 / 链接点击 / 密码提交 / 附件下载 / 举报意识
const selectedRiskDims = computed<RiskDim[]>(() => {
  const emp = selectedEmp.value
  if (!emp) return []
  const s = emp.riskScore
  const dims = [
    { label: '邮件识别', val: Math.min(100, Math.max(5, s - 7)) },
    { label: '链接点击', val: Math.min(100, Math.max(5, s + 6)) },
    { label: '密码提交', val: Math.min(100, Math.max(5, s - 12)) },
    { label: '附件下载', val: Math.min(100, Math.max(5, s - 17)) },
    { label: '举报意识', val: Math.max(5, 100 - s - 12) },
  ]
  return dims.map(d => ({
    label: d.label,
    val: d.val,
    color: d.val > 70 ? '#D85A30' : d.val > 40 ? '#EF9F27' : '#1D9E75',
  }))
})

const trainingPct = computed(() => {
  const s = selectedEmp.value?.training
  if (s === 'completed') return '100%'
  if (s === 'progress') return '60%'
  return '0%'
})

const selectedCourses = computed(() => {
  const s = selectedEmp.value?.training
  return [
    { name: '基础钓鱼防范课程', done: s !== 'none' },
    { name: '密码安全意识培训', done: s === 'completed' },
    { name: '邮件识别专项训练', done: s === 'completed' },
    { name: '社会工程学进阶', done: false },
  ]
})

const selectedReportCount = computed(() => (selectedEmp.value && selectedEmp.value.clicks > 0 ? 2 : 0))

// 历史行为轨迹：按员工中招 / 培训状态动态拼装，对齐 demo 时间轴内容
const selectedTimeline = computed<TimelineEvent[]>(() => {
  const emp = selectedEmp.value
  if (!emp) return []
  const events: TimelineEvent[] = []
  if (emp.clicks > 0) {
    events.push({
      time: '2026-08-15 09:42',
      type: 'danger',
      title: 'Q3全员防钓鱼演练 · 中招',
      desc: '点击钓鱼链接并提交了OA账号密码',
    })
    events.push({
      time: '2026-08-15 10:15',
      type: 'success',
      title: 'Q3全员防钓鱼演练 · 举报',
      desc: '事后意识到风险，通过举报按钮上报可疑邮件',
    })
  }
  if (emp.clicks > 1) {
    events.push({
      time: '2026-06-12 14:20',
      type: 'danger',
      title: 'Q2全员钓鱼演练 · 中招',
      desc: '点击伪造的密码重置链接',
    })
  }
  if (emp.training !== 'none') {
    events.push({
      time: '2026-06-15 16:00',
      type: 'primary',
      title: '安全培训 · 完成',
      desc: '完成「邮件识别专项训练」课程，考核通过',
    })
  }
  if (emp.clicks > 2) {
    events.push({
      time: '2026-03-11 11:08',
      type: 'warning',
      title: 'Q1全公司防钓鱼 · 中招',
      desc: '下载了钓鱼附件中的可执行文件',
    })
  }
  return events.sort((a, b) => b.time.localeCompare(a.time))
})

// ============ 添加/编辑员工弹窗 ============
const empDialogVisible = ref(false)
const empForm = reactive({
  id: 0,
  name: '',
  no: '',
  email: '',
  phone: '',
  dept: '技术部 / 研发组',
  pos: '',
  tags: [] as string[],
  riskScore: 50,
})

function openEmpDialog(row?: Employee) {
  if (row) {
    Object.assign(empForm, {
      id: row.id,
      name: row.name,
      no: row.no,
      email: row.email,
      phone: row.phone,
      dept: row.dept,
      pos: row.pos,
      tags: [...row.tags],
      riskScore: row.riskScore,
    })
  } else {
    Object.assign(empForm, {
      id: 0,
      name: '',
      no: '',
      email: '',
      phone: '',
      dept: '技术部 / 研发组',
      pos: '',
      tags: [],
      riskScore: 50,
    })
  }
  empDialogVisible.value = true
}

function toggleEmpTag(t: string) {
  const idx = empForm.tags.indexOf(t)
  if (idx >= 0) empForm.tags.splice(idx, 1)
  else empForm.tags.push(t)
}

function openTagDialog() {
  newTagName.value = ''
  newTagColor.value = '#378ADD'
  tagDialogVisible.value = true
}

function createTag() {
  const name = newTagName.value.trim()
  if (!name) {
    ElMessage.warning('请输入标签名称')
    return
  }
  if (tagOptions.value.includes(name)) {
    ElMessage.warning('标签已存在')
    return
  }
  tagOptions.value.push(name)
  tagColorMap[name] = newTagColor.value
  ElMessage.success(`标签「${name}」创建成功`)
  tagDialogVisible.value = false
}

function createInlineTag() {
  const name = inlineTagName.value.trim()
  if (!name) {
    inlineTagInputVisible.value = false
    return
  }
  if (!tagOptions.value.includes(name)) {
    tagOptions.value.push(name)
    tagColorMap[name] = '#378ADD'
  }
  if (!empForm.tags.includes(name)) {
    empForm.tags.push(name)
  }
  inlineTagName.value = ''
  inlineTagInputVisible.value = false
}

/** 按「技术部 / 研发组」路径逐级匹配部门树；失败回退根部门，仍无则 1 */
function findDeptId(pathLabel: string): number {
  let nodes = deptTree.value
  let matched: DeptNode | null = null
  for (const seg of pathLabel.split('/').map(s => s.trim()).filter(Boolean)) {
    const hit = nodes.find(n => n.label === seg) ?? null
    if (!hit) break
    matched = hit
    nodes = hit.children ?? []
  }
  if (matched) return matched.id
  return deptTree.value[0]?.id ?? 1
}

async function saveEmp() {
  if (!empForm.name || !empForm.no || !empForm.email) {
    ElMessage.warning('请填写姓名、工号和邮箱')
    return
  }
  const payload = {
    name: empForm.name,
    emp_no: empForm.no,
    email: empForm.email,
    mobile: empForm.phone,
    dept_id: findDeptId(empForm.dept),
    position: empForm.pos,
    tag_ids: [], // TODO: 标签暂未与后端标签体系映射，待接入 orgApi.tags()
    initial_risk: empForm.riskScore,
  }
  try {
    if (empForm.id) await orgApi.updateUser(empForm.id, payload)
    else await orgApi.createUser(payload)
    empDialogVisible.value = false
    ElMessage.success(empForm.id ? '员工信息已更新' : '员工信息已保存，风险画像将自动初始化')
    await loadUsers()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// ============ 工具栏其他按钮（后端暂无对应路由，保留演示行为） ============
function onImportCsv() {
  // TODO: 后端未提供 CSV 批量导入路由
  ElMessage.info('请选择CSV文件导入员工名单（工号、姓名、邮箱必填）')
}
function onExportCsv() {
  // TODO: 后端未提供批量导出路由
  ElMessage.info(`正在导出 ${filteredEmployees.value.length} 条员工数据，请稍候...`)
}
function onSyncAd() {
  // TODO: 后端 depts/sync 仅登记任务，二期接入真实同步
  ElMessage.info('正在连接AD/LDAP服务器同步组织架构...')
}
function onSendDrill(emp: Employee) {
  // TODO: 后端未提供单员工快速发起演练路由，需走演练管理创建流程
  ElMessage.success(`已将「${emp.name}」加入演练发送队列`)
}
</script>

<style scoped lang="scss">
.users-row {
  margin: 0 16px 16px;
}

/* ===== 左侧部门树 ===== */
.dept-card {
  display: flex;
  flex-direction: column;
}
.card-title-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  .title-icon {
    color: var(--color-text-info);
    font-size: 14px;
  }
}
.dept-search {
  margin-bottom: 10px;
}
.dept-tree {
  background: transparent;
  --el-tree-node-hover-bg: var(--color-background-info);
}
.tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 2px 0;
  font-size: 12px;
}
.tree-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-count {
  font-size: 10px;
  color: var(--color-text-tertiary);
  background: var(--color-background-secondary);
  padding: 1px 5px;
  border-radius: 8px;
  margin-left: 6px;
}
.dept-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-tertiary);
  margin-top: 12px;
}
.dept-btn {
  width: 100%;
}

/* ===== 统计卡片 ===== */
.stat-row {
  margin-bottom: 12px;
}

/* ===== 工具栏 ===== */
.toolbar-card {
  padding: 10px 14px;
  margin-bottom: 12px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
}
.toolbar-right {
  flex: 1;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.emp-search {
  width: 220px;
}

/* ===== 表格 ===== */
.table-card {
  padding: 0;
  overflow: hidden;
}
.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #e5e7eb;
}
.selected-info {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.page-size-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
.page-size-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
}
.page-size-select {
  width: 80px;
}
.emp-table {
  font-size: 12px;
}
.emp-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.emp-avatar-sm {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}
.emp-info {
  min-width: 0;
}
.emp-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.emp-no {
  font-size: 10px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}
.risk-score {
  font-size: 11px;
  font-weight: 600;
  margin-left: 4px;
}
.clicks {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-tertiary);
}
.clicks-danger {
  color: #d85a30;
}
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-top: 1px solid #e5e7eb;
}
.page-info {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

/* ===== 右侧风险画像 ===== */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty-card {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}
.profile-head-card {
  padding: 12px 14px;
}
.profile-head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.emp-avatar-lg {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: 500;
  flex-shrink: 0;
}
.profile-head-info {
  flex: 1;
  min-width: 0;
}
.profile-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.profile-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.profile-meta-row {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
  flex-wrap: wrap;
  margin-top: 3px;
}
.mono {
  color: var(--color-text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.card-title-extra {
  font-size: 11px;
  color: var(--color-text-tertiary);
  font-weight: 400;
}
.risk-total {
  font-weight: 600;
  font-size: 13px;
}
.num-danger {
  color: #d85a30;
  font-weight: 600;
}
.num-success {
  color: #1d9e75;
  font-weight: 600;
}

/* 风险画像条状图（对齐 demo .bar-track / .bar-fill / .risk-dim） */
.risk-dim {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  &:last-child {
    margin-bottom: 0;
  }
}
.risk-dim-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  width: 64px;
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
.risk-dim-value {
  font-size: 11px;
  font-weight: 500;
  width: 28px;
  text-align: right;
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* 培训完成度 */
.training-status-wrap {
  text-align: center;
  padding: 6px 0 12px;
}
.training-status {
  font-size: 24px;
  font-weight: 600;
}
.training-sub {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}
.course-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.course-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.course-name {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.course-pending {
  color: var(--color-text-tertiary);
}

/* 时间轴 */
.behavior-timeline {
  padding-left: 8px;
}
.ev-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.ev-desc {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

/* 添加员工弹窗 - 标签芯片 */
.tag-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.tag-chip {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #d1d5db;
  color: var(--color-text-secondary);
  background: var(--color-background-primary);
  &:hover {
    border-color: var(--accent-blue);
  }
  &.selected {
    background: var(--color-background-info);
    color: var(--color-text-info);
    border-color: var(--color-border-info);
  }
  &.tag-chip-add {
    border-style: dashed;
    color: var(--accent-blue);
    border-color: var(--accent-blue);
    background: transparent;
    &:hover {
      background: rgba(55, 138, 221, 0.08);
    }
  }
}

.tag-inline-input {
  width: 140px !important;
  .el-input__wrapper {
    padding: 2px 8px;
    box-shadow: 0 0 0 1px var(--accent-blue) inset;
    border-radius: 6px;
  }
}

.color-picker-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  transition: all 0.2s ease;
  &:hover {
    transform: scale(1.1);
  }
  &.selected {
    border-color: var(--color-text-primary);
    box-shadow: 0 0 0 2px #fff inset, 0 0 0 4px var(--color-text-primary);
  }
}
.tag-add-btn {
  font-size: 12px;
  padding: 0 8px;
}
.risk-slider-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.form-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}
</style>
