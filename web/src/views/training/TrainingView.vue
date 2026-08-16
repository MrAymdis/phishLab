<template>
  <div class="page-container">
    <PageHeader title="安全培训">
      <template #actions>
        <el-button size="small" type="primary" :icon="VideoPlay" @click="openCourseDialog">新建课程</el-button>
        <el-button size="small" :icon="Calendar" @click="openTaskDialog()">新建培训任务</el-button>
        <el-button size="small" :icon="Collection">新建题库</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" style="margin: 8px 16px 0">
      <el-tab-pane label="培训课程库" name="course">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="6"><StatCard title="课程总数" :value="36" accent="blue" /></el-col>
          <el-col :span="6"><StatCard title="视频课程" :value="14" accent="teal" /></el-col>
          <el-col :span="6"><StatCard title="图文课程" :value="12" accent="green" /></el-col>
          <el-col :span="6"><StatCard title="互动课程" :value="10" accent="purple" /></el-col>
        </el-row>
        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-blue">
              <div class="toolbar">
                <el-input v-model="courseKw" size="small" placeholder="搜索课程名称" style="width: 240px" clearable />
                <el-radio-group v-model="categoryFilter" size="small">
                  <el-radio-button value="">全部</el-radio-button>
                  <el-radio-button value="video">视频</el-radio-button>
                  <el-radio-button value="article">图文</el-radio-button>
                  <el-radio-button value="pdf">PDF</el-radio-button>
                  <el-radio-button value="interactive">互动式</el-radio-button>
                </el-radio-group>
                <el-radio-group v-model="levelFilter" size="small">
                  <el-radio-button value="">全部难度</el-radio-button>
                  <el-radio-button value="easy">初级</el-radio-button>
                  <el-radio-button value="mid">中级</el-radio-button>
                  <el-radio-button value="hard">高级</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24" v-if="!filteredCourses.length">
            <el-empty description="暂无符合条件的课程" :image-size="80" />
          </el-col>
          <el-col :span="8" v-for="c in filteredCourses" :key="c.id">
            <div class="card course-card" :class="`card-${c.accent}`">
              <div class="course-cover" :style="{ background: c.coverBg }">
                <span class="cover-icon">{{ c.coverIcon }}</span>
                <el-tag size="small" class="cover-tag" :type="c.tagType">{{ c.typeLabel }}</el-tag>
              </div>
              <div class="course-body">
                <div class="course-title">{{ c.title }}</div>
                <div class="course-meta">
                  <span><el-icon><Clock /></el-icon> {{ c.duration }} 分钟</span>
                  <span>课件：{{ c.material }}</span>
                  <el-tag size="small" :type="levelTagType(c.level)" effect="plain">{{ levelLabel(c.level) }}</el-tag>
                </div>
                <div class="course-stats">
                  <div class="stat">
                    <div class="stat-val">{{ c.learners.toLocaleString() }}</div>
                    <div class="stat-label">学习人数</div>
                  </div>
                  <div class="stat">
                    <div class="stat-val">{{ c.completion }}%</div>
                    <div class="stat-label">平均完成度</div>
                  </div>
                </div>
                <div class="course-actions">
                  <el-button size="small" link>预览</el-button>
                  <el-button size="small" link type="primary">编辑</el-button>
                  <el-button size="small" link type="danger">删除</el-button>
                  <el-divider direction="vertical" />
                  <el-button size="small" link type="success" @click="openTaskDialog(c.id)">新建任务用此课程</el-button>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="培训任务管理" name="task">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="8"><StatCard title="进行中计划" :value="4" accent="green" /></el-col>
          <el-col :span="8"><StatCard title="已完成计划" :value="18" accent="blue" /></el-col>
          <el-col :span="8"><StatCard title="本月覆盖人数" value="3,580" accent="teal" /></el-col>
        </el-row>
        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-green">
              <div class="toolbar">
                <el-button size="small" type="primary" :icon="Plus" @click="openTaskDialog()">新建培训任务</el-button>
                <el-input v-model="taskKw" size="small" placeholder="搜索任务名称" style="width: 220px; margin-left: 12px" clearable />
              </div>
              <el-table :data="taskRows" size="small" style="margin-top: 12px">
                <el-table-column label="任务名称" min-width="200">
                  <template #default="{ row }">
                    <el-link type="primary">{{ row.name }}</el-link>
                  </template>
                </el-table-column>
                <el-table-column label="关联课程" prop="course" min-width="180" />
                <el-table-column label="分配对象" min-width="200">
                  <template #default="{ row }">
                    {{ row.target }}（{{ row.count }} 人）
                  </template>
                </el-table-column>
                <el-table-column label="开始日期" prop="start" width="110" />
                <el-table-column label="截止日期" prop="end" width="110" />
                <el-table-column label="进度" min-width="220">
                  <template #default="{ row }">
                    <div class="task-progress">
                      <el-progress :percentage="row.progress" :stroke-width="8" color="#10B981" />
                      <div class="progress-detail">
                        已开始 {{ row.started }}人 · 已完成 {{ row.done }}人
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.status === 'running'" type="success" size="small">进行中</el-tag>
                    <el-tag v-else-if="row.status === 'completed'" size="small">已完成</el-tag>
                    <el-tag v-else type="danger" size="small">已过期</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="220" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" type="primary">查看详情</el-button>
                    <el-button link size="small" type="warning" v-if="row.status === 'running'">催办</el-button>
                    <el-button link size="small">导出证明</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-pagination
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, sizes, prev, pager, next"
                :total="42"
                :page-sizes="[10, 20, 50]"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="考试与测评" name="exam">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="6"><StatCard title="题库总数" value="248" suffix=" 道" accent="blue" /></el-col>
          <el-col :span="6"><StatCard title="试卷总数" value="15" suffix=" 份" accent="purple" /></el-col>
          <el-col :span="6"><StatCard title="本月考试次数" value="3,940" accent="teal" /></el-col>
          <el-col :span="6">
            <div class="card card-orange" style="height: 100%; display: flex; align-items: center; justify-content: center">
              <el-button type="primary" :icon="Plus">新建题目</el-button>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-red">
              <div class="card-title">题目列表</div>
              <el-table :data="questionRows" size="small" style="margin-top: 8px">
                <el-table-column label="题型" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.type === 'single'" type="primary" size="small">单选</el-tag>
                    <el-tag v-else-if="row.type === 'multi'" type="warning" size="small">多选</el-tag>
                    <el-tag v-else type="info" size="small">判断</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="题干" min-width="320" prop="content" show-overflow-tooltip />
                <el-table-column label="答案选项" min-width="200">
                  <template #default="{ row }">
                    <span v-if="row.type === 'judge'">正确 / 错误</span>
                    <span v-else>{{ row.options }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="难度" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.diff === 'hard'" type="danger" size="small">难</el-tag>
                    <el-tag v-else-if="row.diff === 'mid'" type="warning" size="small">中</el-tag>
                    <el-tag v-else type="success" size="small">易</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="关联课程" prop="course" min-width="160" show-overflow-tooltip />
                <el-table-column label="操作" width="130" fixed="right">
                  <template #default>
                    <el-button link size="small" type="primary">编辑</el-button>
                    <el-button link size="small" type="danger">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-pagination
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, sizes, prev, pager, next"
                :total="186"
                :page-sizes="[10, 20, 50]"
              />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-purple">
              <div class="card-title">
                组卷管理
                <el-button size="small" type="primary" :icon="Document" style="margin-left: 12px">新建试卷</el-button>
              </div>
              <el-table :data="paperRows" size="small" style="margin-top: 8px">
                <el-table-column label="试卷名称" min-width="200">
                  <template #default="{ row }">
                    <el-link type="primary">{{ row.name }}</el-link>
                  </template>
                </el-table-column>
                <el-table-column label="题数（单/多/判）" width="160" align="center">
                  <template #default="{ row }">
                    {{ row.single }} + {{ row.multi }} + {{ row.judge }}
                    <span style="color: var(--color-text-secondary); margin-left: 4px">= {{ row.single + row.multi + row.judge }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="总分" width="70" align="center" prop="total" />
                <el-table-column label="通关分数线" width="100" align="center">
                  <template #default="{ row }">{{ row.pass }} 分（{{ row.passPct }}%）</template>
                </el-table-column>
                <el-table-column label="已发布次数" width="110" align="center" prop="publishCount" />
                <el-table-column label="操作" width="260" fixed="right">
                  <template #default>
                    <el-button link size="small">预览</el-button>
                    <el-button link size="small" type="success">发布</el-button>
                    <el-button link size="small" type="primary">编辑</el-button>
                    <el-button link size="small">导出试卷</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="taskDialogVisible" title="新建培训任务" width="620px">
      <el-form :model="taskForm" label-width="120px">
        <el-form-item label="选择课程">
          <el-select v-model="taskForm.courseId" style="width: 100%" placeholder="请选择课程">
            <el-option label="《信息安全基础规范》" :value="1" />
            <el-option label="《钓鱼邮件识别入门》" :value="2" />
            <el-option label="《钓鱼邮件识别进阶》" :value="3" />
            <el-option label="《企业数据安全红线》" :value="4" />
            <el-option label="《财务人员专项安全课》" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="人员选择">
          <el-select v-model="taskForm.targets" multiple filterable style="width: 100%" placeholder="选择部门/组/人员">
            <el-option-group label="部门">
              <el-option label="财务部（56人）" value="dept_finance" />
              <el-option label="市场部（128人）" value="dept_marketing" />
              <el-option label="行政部（32人）" value="dept_admin" />
              <el-option label="人力资源部（28人）" value="dept_hr" />
              <el-option label="技术部（156人）" value="dept_tech" />
              <el-option label="研发部（342人）" value="dept_rd" />
            </el-option-group>
            <el-option-group label="分组">
              <el-option label="高管组（12人）" value="grp_exec" />
              <el-option label="全员（3580人）" value="grp_all" />
              <el-option label="新员工组（30人）" value="grp_new" />
            </el-option-group>
            <el-option-group label="人员">
              <el-option label="张小明（财务部）" value="u_001" />
              <el-option label="李晓华（市场部）" value="u_002" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="taskForm.deadline"
            type="datetime"
            style="width: 100%"
            placeholder="选择截止日期"
          />
        </el-form-item>
        <el-form-item label="自动推送规则">
          <el-switch v-model="taskForm.autoAssign" />
          <span style="margin-left: 8px; color: var(--color-text-secondary); font-size: 12px">
            演练中招后自动分配给中招人员
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTask">创建任务</el-button>
      </template>
    </el-dialog>

    <!-- ============ 新建课程弹窗 ============ -->
    <el-dialog v-model="courseDialogVisible" title="新建课程" width="600px" destroy-on-close>
      <el-form :model="courseForm" label-width="100px">
        <el-form-item label="课程名称" required>
          <el-input v-model="courseForm.name" placeholder="如：《钓鱼邮件识别进阶》" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="课程类型">
              <el-select v-model="courseForm.type" style="width: 100%">
                <el-option label="视频" value="video" />
                <el-option label="图文" value="article" />
                <el-option label="PDF" value="pdf" />
                <el-option label="互动小游戏" value="interactive" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="难度等级">
              <el-select v-model="courseForm.level" style="width: 100%">
                <el-option label="初级" value="easy" />
                <el-option label="中级" value="mid" />
                <el-option label="高级" value="hard" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="课程时长">
          <el-input-number v-model="courseForm.duration" :min="5" :max="240" :step="5" />
          <span style="margin-left: 8px; color: var(--color-text-secondary); font-size: 12px">分钟</span>
        </el-form-item>
        <el-form-item label="课程描述">
          <el-input v-model="courseForm.desc" type="textarea" :rows="3" placeholder="课程目标、适用人群、内容简介" />
        </el-form-item>
        <el-form-item label="上传课件">
          <el-upload drag action="#" :auto-upload="false" style="width: 100%">
            <el-icon :size="36" color="var(--color-text-tertiary)"><UploadFilled /></el-icon>
            <div style="font-size: 13px; margin-top: 6px">拖拽课件文件到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div style="font-size: 11px; color: var(--color-text-tertiary)">支持 mp4 / pptx / pdf / html，单个文件不超过 500MB</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCourse">创建课程</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, Calendar, Collection, Plus, Clock, Document, UploadFilled } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import { trainingApi } from '@/api'

const activeTab = ref('course')
const courseKw = ref('')
const categoryFilter = ref('')
const levelFilter = ref('')
const taskKw = ref('')
const taskDialogVisible = ref(false)

const taskForm = reactive({
  courseId: null as number | null,
  targets: [] as string[],
  deadline: '',
  autoAssign: false,
})

const openTaskDialog = (courseId?: number) => {
  if (courseId) taskForm.courseId = courseId
  taskDialogVisible.value = true
}

// ============ 新建课程弹窗 ============
const courseDialogVisible = ref(false)
const courseForm = reactive({
  name: '',
  type: 'video',
  level: 'easy',
  duration: 20,
  desc: '',
})

function openCourseDialog() {
  Object.assign(courseForm, { name: '', type: 'video', level: 'easy', duration: 20, desc: '' })
  courseDialogVisible.value = true
}

async function saveCourse() {
  if (!courseForm.name) {
    ElMessage.warning('请填写课程名称')
    return
  }
  try {
    await trainingApi.createCourse({ ...courseForm })
    courseDialogVisible.value = false
    ElMessage.success('课程已创建')
    loadCourses()
  } catch { /* 拦截器已提示 */ }
}

async function saveTask() {
  if (!taskForm.courseId) {
    ElMessage.warning('请选择课程')
    return
  }
  try {
    await trainingApi.createTask({ ...taskForm })
    taskDialogVisible.value = false
    ElMessage.success('培训任务已创建')
    loadTasks()
  } catch { /* 拦截器已提示 */ }
}

function levelLabel(level: string) {
  return level === 'easy' ? '初级' : level === 'mid' ? '中级' : '高级'
}

function levelTagType(level: string) {
  return level === 'easy' ? 'success' : level === 'mid' ? 'warning' : 'danger'
}

const accentList = ['blue', 'green', 'orange', 'purple', 'red', 'teal'] as const
const courseMocks = [
  { id: 1, title: '《信息安全基础规范》', type: 'video', typeLabel: '视频', tagType: 'primary' as const, level: 'easy', material: '视频课件', duration: 28, learners: 3420, completion: 91, accent: accentList[0], coverBg: 'linear-gradient(135deg, #378ADD, #1E5FA8)', coverIcon: '🛡️' },
  { id: 2, title: '《钓鱼邮件识别入门》', type: 'article', typeLabel: '图文', tagType: 'success' as const, level: 'easy', material: '图文+PDF', duration: 18, learners: 3210, completion: 88, accent: accentList[1], coverBg: 'linear-gradient(135deg, #10B981, #059669)', coverIcon: '📧' },
  { id: 3, title: '《钓鱼邮件识别进阶》', type: 'interactive', typeLabel: '互动式', tagType: 'warning' as const, level: 'hard', material: '场景模拟', duration: 45, learners: 2156, completion: 72, accent: accentList[2], coverBg: 'linear-gradient(135deg, #F59E0B, #D97706)', coverIcon: '🎯' },
  { id: 4, title: '《企业数据安全红线》', type: 'pdf', typeLabel: 'PDF', tagType: 'info' as const, level: 'mid', material: 'PDF文档', duration: 12, learners: 2980, completion: 85, accent: accentList[3], coverBg: 'linear-gradient(135deg, #8E7CC3, #5B4B8A)', coverIcon: '📕' },
  { id: 5, title: '《财务人员专项安全课》', type: 'video', typeLabel: '视频', tagType: 'primary' as const, level: 'hard', material: '视频+案例', duration: 52, learners: 580, completion: 68, accent: accentList[4], coverBg: 'linear-gradient(135deg, #EF4444, #B91C1C)', coverIcon: '💰' },
  { id: 6, title: '《新员工入职安全培训》', type: 'interactive', typeLabel: '互动式', tagType: 'warning' as const, level: 'mid', material: '完整培训包', duration: 90, learners: 186, completion: 92, accent: accentList[5], coverBg: 'linear-gradient(135deg, #14B8A6, #0D9488)', coverIcon: '👋' },
]
const courses = ref([...courseMocks])

// 类型 + 难度 + 关键词组合过滤（供课程卡片渲染）
const filteredCourses = computed(() => {
  const kw = courseKw.value.trim().toLowerCase()
  return courses.value.filter(c => {
    if (categoryFilter.value && c.type !== categoryFilter.value) return false
    if (levelFilter.value && c.level !== levelFilter.value) return false
    if (kw && !c.title.toLowerCase().includes(kw)) return false
    return true
  })
})

const taskMocks = [
  { name: 'Q3全员安全意识强化任务', course: '《信息安全基础规范》', target: '全员', count: 3580, start: '2026-08-01', end: '2026-08-31', started: 2860, done: 1920, progress: 54, status: 'running' },
  { name: '财务中招人员强制培训', course: '《财务人员专项安全课》', target: '财务部', count: 56, start: '2026-08-10', end: '2026-08-20', started: 52, done: 38, progress: 68, status: 'running' },
  { name: '高管专项合规培训', course: '《企业数据安全红线》', target: '高管组', count: 12, start: '2026-07-15', end: '2026-07-31', started: 12, done: 12, progress: 100, status: 'completed' },
  { name: 'Q2新员工入职培训', course: '《新员工入职安全培训》', target: '新员工组', count: 28, start: '2026-06-20', end: '2026-07-10', started: 28, done: 26, progress: 93, status: 'completed' },
  { name: '5月钓鱼识别进阶训练', course: '《钓鱼邮件识别进阶》', target: '市场+行政', count: 160, start: '2026-05-01', end: '2026-05-20', started: 142, done: 118, progress: 74, status: 'expired' },
  { name: '研发部安全基础测评', course: '《信息安全基础规范》', target: '研发部', count: 342, start: '2026-04-10', end: '2026-04-30', started: 342, done: 342, progress: 100, status: 'completed' },
]
const taskRows = ref([...taskMocks])

const questionMocks = [
  { type: 'single', content: '收到一封来自"HR@company.com"的邮件，要求点击链接更新工资卡信息，最合理的做法是？', options: 'A.直接点击链接 B.回复邮件确认 C.通过企业微信找HR核实 D.转发给同事', diff: 'easy', course: '《钓鱼邮件识别入门》' },
  { type: 'multi', content: '以下哪些属于常见的钓鱼攻击手法？（多选）', options: '仿冒OA登录页 / 伪造快递签收短信 / 正常会议邀请', diff: 'mid', course: '《钓鱼邮件识别进阶》' },
  { type: 'judge', content: '邮件中只要有公司logo和发件人域名正确，就可以放心点击链接。', options: '', diff: 'easy', course: '《信息安全基础规范》' },
  { type: 'single', content: '在公共场合发现写有"工资单"字样的U盘，正确做法是？', options: 'A.插入电脑查看 B.带回家再看 C.交给IT部门处理 D.丢到垃圾桶', diff: 'mid', course: '《企业数据安全红线》' },
  { type: 'multi', content: '发现可疑邮件后，可以采取以下哪些正确措施？', options: '点击举报按钮 / 转发给IT安全团队 / 直接回复询问发件人', diff: 'hard', course: '《钓鱼邮件识别进阶》' },
  { type: 'judge', content: '为了方便记忆，可以将多个系统的密码设置为同一个强密码。', options: '', diff: 'mid', course: '《信息安全基础规范》' },
  { type: 'single', content: '收到要求紧急转账的"财务总监"微信消息，应该？', options: 'A.立即转账 B.电话或当面确认 C.回复确认账号 D.先转一半', diff: 'hard', course: '《财务人员专项安全课》' },
]
const questionRows = ref([...questionMocks])

const paperMocks = [
  { name: 'Q3全员信息安全摸底考试', single: 10, multi: 5, judge: 5, total: 100, pass: 80, passPct: 80, publishCount: 3 },
  { name: '财务人员专项测评（高级）', single: 15, multi: 8, judge: 7, total: 100, pass: 75, passPct: 75, publishCount: 2 },
  { name: '新员工入职安全结业考试', single: 12, multi: 4, judge: 4, total: 100, pass: 70, passPct: 70, publishCount: 5 },
  { name: '钓鱼邮件识别月度考核', single: 8, multi: 6, judge: 6, total: 100, pass: 80, passPct: 80, publishCount: 4 },
  { name: '高管合规专项试卷', single: 10, multi: 6, judge: 4, total: 100, pass: 85, passPct: 85, publishCount: 1 },
]
const paperRows = ref([...paperMocks])

// ============ 接口加载（失败时保留演示数据） ============
const courseTypeLabel: Record<string, string> = { video: '视频', article: '图文', pdf: 'PDF', interactive: '互动式' }
const courseTagType: Record<string, string> = { video: 'primary', article: 'success', interactive: 'warning', pdf: 'info' }

async function loadCourses() {
  try {
    const list = (await trainingApi.courses()) as Array<Record<string, any>>
    if (Array.isArray(list) && list.length) {
      courses.value = list.map((c, i) => ({
        ...c,
        typeLabel: courseTypeLabel[c.type] ?? c.type,
        tagType: courseTagType[c.type] ?? 'primary',
        accent: accentList[i % accentList.length],
        coverBg: courseMocks[i]?.coverBg ?? courseMocks[0].coverBg,
        coverIcon: courseMocks[i]?.coverIcon ?? courseMocks[0].coverIcon,
      })) as typeof courseMocks
    }
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

async function loadTasks() {
  try {
    const list = (await trainingApi.tasks()) as Array<Record<string, any>>
    if (Array.isArray(list) && list.length) taskRows.value = list as typeof taskMocks
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

async function loadQuestionBank() {
  try {
    const list = (await trainingApi.questionBank()) as Array<Record<string, any>>
    if (Array.isArray(list) && list.length) {
      // 后端 options 为数组，转为与演示数据一致的分隔字符串
      questionRows.value = list.map(q => ({
        ...q,
        options: Array.isArray(q.options) ? q.options.join(' / ') : q.options,
      })) as typeof questionMocks
    }
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

async function loadPapers() {
  try {
    const list = (await trainingApi.papers()) as Array<Record<string, any>>
    if (Array.isArray(list) && list.length) paperRows.value = list as typeof paperMocks
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

onMounted(() => {
  loadCourses()
  loadTasks()
  loadQuestionBank()
  loadPapers()
})
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.course-card {
  padding: 0;
  overflow: hidden;
}
.course-cover {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.cover-icon {
  font-size: 48px;
  opacity: 0.9;
}
.cover-tag {
  position: absolute;
  top: 10px;
  right: 10px;
}
.course-body {
  padding: 12px 14px 14px;
}
.course-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}
.course-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  .el-icon { vertical-align: middle; margin-right: 2px; }
}
.course-stats {
  display: flex;
  padding: 10px;
  background: var(--color-background-secondary);
  border-radius: 8px;
  margin-bottom: 10px;
}
.stat {
  flex: 1;
  text-align: center;
  &:not(:last-child) { border-right: 1px solid var(--color-border-tertiary); }
}
.stat-val {
  font-size: 16px;
  font-weight: 600;
}
.stat-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.course-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.task-progress {
  .progress-detail {
    font-size: 11px;
    color: var(--color-text-tertiary);
    margin-top: 4px;
  }
}
</style>
