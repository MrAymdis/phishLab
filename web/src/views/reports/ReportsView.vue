<template>
  <div class="page-container">
    <PageHeader title="数据报表">
      <template #actions>
        <el-button size="small" :icon="Refresh">刷新数据</el-button>
        <div class="chatbi-input">
          <el-input v-model="chatbiQuery" size="small" placeholder="自然语言问数，如:上月财务部中招率" style="width: 320px">
            <template #append>
              <el-button type="primary" :icon="Promotion">发送</el-button>
            </template>
          </el-input>
        </div>
        <el-button size="small" :icon="Document">导出 PDF</el-button>
        <el-button size="small" :icon="DocumentCopy">导出 Excel</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" style="margin: 8px 16px 0">
      <el-tab-pane label="演练报表" name="drill">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="8">
            <div class="card card-blue">
              <div class="card-title">选择演练</div>
              <el-select v-model="selectedDrill" size="default" style="width: 100%; margin-top: 8px">
                <el-option label="Q3全员防钓鱼演练" value="q3_all" />
                <el-option label="Q2全员钓鱼演练" value="q2_all" />
                <el-option label="新员工入职演练（8月）" value="new_emp" />
                <el-option label="财务专项演练" value="finance" />
                <el-option label="高管针对性演练" value="exec" />
              </el-select>
            </div>
          </el-col>
          <el-col :span="5">
            <StatCard title="综合得分" value="82" suffix=" 分" accent="teal" />
          </el-col>
          <el-col :span="5">
            <StatCard title="关键发现" value="4" suffix=" 条" accent="orange" />
          </el-col>
          <el-col :span="6">
            <StatCard title="改进建议" value="3" suffix=" 条" accent="purple" />
          </el-col>
        </el-row>

        <!-- 核心行为指标 -->
        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="4" v-for="m in drillMetrics" :key="m.title">
            <StatCard :title="m.title" :value="m.value" :suffix="m.suffix" :sub="m.sub" :accent="m.accent" />
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="12">
            <div class="card card-orange">
              <div class="card-title">转化漏斗分析</div>
              <FunnelChart :items="drillFunnel" height="320px" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-blue">
              <div class="card-title">演练期间每日趋势</div>
              <BaseChart :option="dailyTrendChart" height="320px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-purple">
              <div class="card-title">部门对比明细</div>
              <el-table :data="deptCompareRows" size="small" style="margin-top: 8px">
                <el-table-column label="部门" prop="dept" min-width="140" />
                <el-table-column label="发送数" prop="sent" width="100" align="center" />
                <el-table-column label="中招数" prop="victim" width="100" align="center" />
                <el-table-column label="中招率" width="110" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.victimRate >= 25 ? '#dc2626' : row.victimRate >= 15 ? '#d97706' : '#16a34a', fontWeight: 600 }">
                      {{ row.victimRate }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="举报数" prop="report" width="100" align="center" />
                <el-table-column label="举报率" width="110" align="center">
                  <template #default="{ row }">{{ row.reportRate }}%</template>
                </el-table-column>
                <el-table-column label="状态" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.victimRate >= 25" type="danger" size="small">重点关注</el-tag>
                    <el-tag v-else-if="row.victimRate >= 15" type="warning" size="small">持续观察</el-tag>
                    <el-tag v-else type="success" size="small">表现良好</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-red">
              <div class="card-title">中招明细</div>
              <el-table :data="victimRows" size="small" style="margin-top: 8px">
                <el-table-column label="姓名" prop="name" width="90" />
                <el-table-column label="部门" prop="dept" width="120" />
                <el-table-column label="邮箱" prop="email" min-width="200" />
                <el-table-column label="首次打开时间" prop="first_open" width="160" />
                <el-table-column label="点击次数" prop="clicks" width="80" align="center" />
                <el-table-column label="是否输入密码" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.input_pwd" type="danger" size="small">是</el-tag>
                    <el-tag v-else type="info" size="small">否</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="风险等级" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.risk === 'high'" type="danger" size="small">高危</el-tag>
                    <el-tag v-else-if="row.risk === 'mid'" type="warning" size="small">中危</el-tag>
                    <el-tag v-else type="success" size="small">低危</el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-pagination
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, sizes, prev, pager, next"
                :total="187"
                :page-sizes="[10, 20, 50, 100]"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="部门报表" name="dept">
        <!-- 时间范围筛选 -->
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="24">
            <div class="card card-blue">
              <div class="toolbar">
                <span style="font-size: 12px; color: var(--color-text-tertiary)">统计周期：</span>
                <el-radio-group v-model="deptRange" size="small">
                  <el-radio-button value="7d">近7天</el-radio-button>
                  <el-radio-button value="month">本月</el-radio-button>
                  <el-radio-button value="quarter">本季度</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="12">
            <div class="card card-purple">
              <div class="card-title">各部门安全意识横向对比（中招率%）</div>
              <BaseChart :option="deptBarChart" height="420px" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-green">
              <div class="card-title">
                <el-select v-model="selectedDept" size="small" style="width: 180px">
                  <el-option label="全部部门" value="all" />
                  <el-option label="财务部" value="finance" />
                  <el-option label="市场部" value="marketing" />
                  <el-option label="行政部" value="admin" />
                  <el-option label="人力资源部" value="hr" />
                  <el-option label="技术部" value="tech" />
                  <el-option label="研发部" value="rd" />
                  <el-option label="法务部" value="legal" />
                </el-select>
                <span style="margin-left: 8px">人员明细</span>
              </div>
              <el-table :data="deptPersonRows" size="small" style="margin-top: 8px">
                <el-table-column label="姓名" prop="name" width="80" />
                <el-table-column label="部门" prop="dept" width="100" />
                <el-table-column label="岗位" prop="role" width="100" />
                <el-table-column label="参与次数" prop="drills" width="80" align="center" />
                <el-table-column label="中招率" prop="rate" width="90" align="center">
                  <template #default="{ row }">{{ row.rate }}%</template>
                </el-table-column>
                <el-table-column label="风险" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.rate >= 25" type="danger" size="small">高</el-tag>
                    <el-tag v-else-if="row.rate >= 15" type="warning" size="small">中</el-tag>
                    <el-tag v-else type="success" size="small">低</el-tag>
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

        <!-- 部门维度明细表 -->
        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-teal">
              <div class="card-title">部门维度明细</div>
              <el-table :data="deptDetailRows" size="small" style="margin-top: 8px">
                <el-table-column label="部门" prop="dept" min-width="140" />
                <el-table-column label="总人数" prop="total" width="90" align="center" />
                <el-table-column label="覆盖次数" prop="coverage" width="90" align="center" />
                <el-table-column label="中招次数" prop="victim" width="90" align="center" />
                <el-table-column label="平均中招率" width="110" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.avgRate >= 25 ? '#dc2626' : row.avgRate >= 15 ? '#d97706' : '#16a34a', fontWeight: 600 }">
                      {{ row.avgRate }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="举报数" prop="report" width="90" align="center" />
                <el-table-column label="培训完成率" width="110" align="center">
                  <template #default="{ row }">{{ row.trainRate }}%</template>
                </el-table-column>
                <el-table-column label="风险评级" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.avgRate >= 25" type="danger" size="small">高风险</el-tag>
                    <el-tag v-else-if="row.avgRate >= 15" type="warning" size="small">中风险</el-tag>
                    <el-tag v-else type="success" size="small">低风险</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default>
                    <el-button size="small" link type="primary">下钻分析</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="综合趋势" name="trend">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="24">
            <div class="card card-teal">
              <div class="card-title">
                <div class="trend-filter">
                  <el-radio-group v-model="trendRange" size="small">
                    <el-radio-button value="3m">近3月</el-radio-button>
                    <el-radio-button value="6m">近半年</el-radio-button>
                    <el-radio-button value="1y">近一年</el-radio-button>
                  </el-radio-group>
                  <el-checkbox-group v-model="sceneCheck" size="small" style="margin-left: 20px">
                    <el-checkbox label="finance">财务类</el-checkbox>
                    <el-checkbox label="hr">HR类</el-checkbox>
                    <el-checkbox label="sys">系统类</el-checkbox>
                  </el-checkbox-group>
                </div>
              </div>
              <BaseChart :option="trendChart" height="340px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-blue">
              <div class="card-title">场景防范意识表</div>
              <el-table :data="sceneRows" size="small" style="margin-top: 8px">
                <el-table-column label="场景名称" prop="name" min-width="160" />
                <el-table-column label="演练次数" prop="count" width="100" align="center" />
                <el-table-column label="平均中招率" prop="rate" width="110" align="center">
                  <template #default="{ row }">{{ row.rate }}%</template>
                </el-table-column>
                <el-table-column label="整体评价" min-width="200">
                  <template #default="{ row }">
                    <el-tag v-if="row.rate >= 25" type="danger" size="small">需重点培训</el-tag>
                    <el-tag v-else-if="row.rate >= 15" type="warning" size="small">需持续关注</el-tag>
                    <el-tag v-else type="success" size="small">意识良好</el-tag>
                    <span style="margin-left: 8px; color: var(--color-text-secondary); font-size: 12px">{{ row.comment }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>

        <!-- 趋势总结卡片 -->
        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="8">
            <div class="card card-green">
              <div class="card-title">安全意识提升率</div>
              <div class="summary-big">59.1<span class="summary-unit">%</span></div>
              <div class="summary-desc">近一年中招率由 32% 降至 13.1%，整体安全意识显著提升</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="card card-red">
              <div class="card-title">最薄弱场景</div>
              <div class="summary-big danger">财务类</div>
              <div class="summary-desc">平均中招率 36%，建议针对财务条线开展高频专项演练</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="card card-blue">
              <div class="card-title">最佳改进部门</div>
              <div class="summary-big info">研发中心</div>
              <div class="summary-desc">中招率环比下降 42%，培训完成率提升至 96%</div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="员工个人报表" name="person">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="8">
            <div class="card card-blue">
              <div class="card-title">搜索员工</div>
              <el-input v-model="personKw" size="default" placeholder="输入姓名 / 工号" style="margin-top: 8px" clearable />
            </div>
          </el-col>
          <el-col :span="16">
            <div class="card card-teal">
              <div class="person-card">
                <div class="avatar-block">{{ selectedPerson.name.slice(0, 1) }}</div>
                <div class="person-info">
                  <div class="person-name">{{ selectedPerson.name }}</div>
                  <div class="person-meta">
                    <span>工号：{{ selectedPerson.empId }}</span>
                    <span>部门：{{ selectedPerson.dept }}</span>
                    <span>岗位：{{ selectedPerson.role }}</span>
                    <span>入职：{{ selectedPerson.hireDate }}</span>
                  </div>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="12">
            <div class="card card-orange">
              <div class="card-title">五维能力雷达（个人风险画像）</div>
              <BaseChart :option="radarChart" height="300px" />
              <div class="risk-score">
                <span style="margin-right: 12px">个人风险值总分：</span>
                <el-progress :percentage="68" :stroke-width="14" color="#D85A30" style="flex: 1" />
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-purple">
              <div class="card-title">历史行为轨迹</div>
              <el-timeline style="margin-top: 4px">
                <el-timeline-item
                  v-for="(e, idx) in timelineEvents"
                  :key="idx"
                  :timestamp="e.time"
                  :type="e.type"
                  :hollow="e.hollow"
                  placement="top"
                >
                  {{ e.text }}
                </el-timeline-item>
              </el-timeline>
            </div>
          </el-col>
        </el-row>

        <!-- 个人风险值变化趋势 -->
        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-red">
              <div class="card-title">个人风险值变化趋势（近6月）</div>
              <BaseChart :option="personRiskTrend" height="240px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-green">
              <div class="card-title">培训完成记录</div>
              <el-table :data="trainRows" size="small" style="margin-top: 8px">
                <el-table-column label="课程名称" prop="course" min-width="200" />
                <el-table-column label="完成日期" prop="date" width="130" />
                <el-table-column label="考试分数" prop="score" width="100" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.score >= 80 ? '#2b8a3e' : row.score >= 60 ? '#d97706' : '#dc2626', fontWeight: 600 }">
                      {{ row.score }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="通关状态" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.score >= 80" type="success" size="small">已通关</el-tag>
                    <el-tag v-else-if="row.score >= 60" type="warning" size="small">补考通过</el-tag>
                    <el-tag v-else type="danger" size="small">未通过</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { Refresh, Promotion, Document, DocumentCopy } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import BaseChart from '@/components/base/BaseChart.vue'
import FunnelChart from '@/components/business/FunnelChart.vue'

const activeTab = ref('drill')
const chatbiQuery = ref('')
const selectedDrill = ref('q3_all')
const selectedDept = ref('all')
const deptRange = ref('month')
const trendRange = ref('3m')
const sceneCheck = ref(['finance', 'hr', 'sys'])
const personKw = ref('张小明')

const drillFunnel = [
  { name: '发送成功', value: 1200, rate: '100%' },
  { name: '已阅读', value: 856, rate: '71.3%' },
  { name: '已点击', value: 324, rate: '→37.8%' },
  { name: '输入数据', value: 187, rate: '→57.7%' },
  { name: '已举报', value: 268, rate: '31.3%' },
  { name: '附件运行', value: 62, rate: '→23.1%' },
]

// 演练核心行为指标（对齐原型：发送/打开/点击/中招/举报）
type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const drillMetrics: { title: string; value: string | number; suffix: string; sub: string; accent: Accent }[] = [
  { title: '发送数', value: '2,000', suffix: ' 封', sub: '覆盖 5 个部门', accent: 'blue' },
  { title: '打开数', value: '1,450', suffix: ' 封', sub: '打开率 72.5%', accent: 'teal' },
  { title: '点击数', value: '520', suffix: ' 次', sub: '点击率 26.0%', accent: 'orange' },
  { title: '中招数', value: '320', suffix: ' 人', sub: '中招率 16.0%', accent: 'red' },
  { title: '举报数', value: '186', suffix: ' 封', sub: '举报率 9.3%', accent: 'green' },
]

// 演练期间每日趋势（打开/点击/中招）
const dailyTrendChart: EChartsOption = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['打开', '点击', '中招'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 20, top: 34, bottom: 30 },
  xAxis: { type: 'category', data: ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'] },
  yAxis: { type: 'value' },
  series: [
    { name: '打开', type: 'line', smooth: true, data: [520, 380, 210, 140, 96, 62, 42], itemStyle: { color: '#378ADD' }, areaStyle: { opacity: 0.08 } },
    { name: '点击', type: 'line', smooth: true, data: [168, 122, 96, 62, 41, 20, 11], itemStyle: { color: '#D85A30' } },
    { name: '中招', type: 'line', smooth: true, data: [98, 78, 61, 42, 25, 11, 5], itemStyle: { color: '#A32D2D' } },
  ],
}

// 部门对比明细
const deptCompareRows = [
  { dept: '财务部', sent: 420, victim: 134, victimRate: 32, report: 38, reportRate: 9.0 },
  { dept: '市场部', sent: 560, victim: 146, victimRate: 26, report: 51, reportRate: 9.1 },
  { dept: '行政部', sent: 280, victim: 59, victimRate: 21, report: 30, reportRate: 10.7 },
  { dept: '人力资源部', sent: 240, victim: 41, victimRate: 17, report: 26, reportRate: 10.8 },
  { dept: '技术部', sent: 500, victim: 45, victimRate: 9, report: 41, reportRate: 8.2 },
]

// 部门维度明细（部门报表）
const deptDetailRows = [
  { dept: '财务部', total: 56, coverage: 8, victim: 34, avgRate: 32, report: 12, trainRate: 68 },
  { dept: '市场部', total: 218, coverage: 7, victim: 118, avgRate: 26, report: 24, trainRate: 72 },
  { dept: '行政部', total: 78, coverage: 8, victim: 33, avgRate: 21, report: 11, trainRate: 78 },
  { dept: '人力资源部', total: 45, coverage: 7, victim: 15, avgRate: 17, report: 9, trainRate: 82 },
  { dept: '技术部', total: 892, coverage: 8, victim: 160, avgRate: 9, report: 86, trainRate: 94 },
]

const victimRows = [
  { name: '张小明', dept: '财务部', email: 'zhangxm@example.com', first_open: '2026-08-15 09:32:11', clicks: 5, input_pwd: true, risk: 'high' },
  { name: '李晓华', dept: '市场部', email: 'lixh@example.com', first_open: '2026-08-15 10:05:42', clicks: 3, input_pwd: true, risk: 'high' },
  { name: '王建国', dept: '行政部', email: 'wangjg@example.com', first_open: '2026-08-15 11:20:08', clicks: 2, input_pwd: false, risk: 'mid' },
  { name: '赵丽娟', dept: '财务部', email: 'zhaolj@example.com', first_open: '2026-08-15 13:44:51', clicks: 4, input_pwd: true, risk: 'high' },
  { name: '陈志强', dept: '研发部', email: 'chenzq@example.com', first_open: '2026-08-15 14:10:23', clicks: 1, input_pwd: false, risk: 'low' },
  { name: '孙美玲', dept: '人力资源部', email: 'sunml@example.com', first_open: '2026-08-15 15:02:17', clicks: 2, input_pwd: false, risk: 'mid' },
  { name: '周文博', dept: '技术部', email: 'zhouwb@example.com', first_open: '2026-08-15 16:38:05', clicks: 1, input_pwd: false, risk: 'low' },
  { name: '吴慧敏', dept: '法务部', email: 'wuhm@example.com', first_open: '2026-08-16 08:15:49', clicks: 0, input_pwd: false, risk: 'low' },
]

const deptBarChart: EChartsOption = {
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 90, right: 40, top: 20, bottom: 30 },
  xAxis: { type: 'value', name: '中招率%', max: 40 },
  yAxis: {
    type: 'category',
    data: ['法务部', '技术部', '研发部', '人力资源部', '行政部', '市场部', '财务部'],
  },
  series: [{
    type: 'bar',
    barWidth: 22,
    data: [8, 9, 11, 17, 21, 26, 32],
    itemStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [
          { offset: 0, color: '#8E7CC3' },
          { offset: 1, color: '#5B4B8A' },
        ],
      },
      borderRadius: [0, 4, 4, 0],
    },
    label: { show: true, position: 'right', formatter: '{c}%', fontSize: 11 },
  }],
}

const deptPersonRows = [
  { name: '张小明', dept: '财务部', role: '会计', drills: 8, rate: 42 },
  { name: '赵丽娟', dept: '财务部', role: '出纳', drills: 8, rate: 38 },
  { name: '李晓华', dept: '市场部', role: '市场专员', drills: 7, rate: 33 },
  { name: '钱海涛', dept: '市场部', role: '市场经理', drills: 7, rate: 28 },
  { name: '王建国', dept: '行政部', role: '行政主管', drills: 8, rate: 24 },
  { name: '孙美玲', dept: '人力资源部', role: 'HRBP', drills: 7, rate: 19 },
  { name: '陈志强', dept: '研发部', role: '高级工程师', drills: 8, rate: 11 },
  { name: '周文博', dept: '技术部', role: '运维工程师', drills: 8, rate: 9 },
  { name: '吴慧敏', dept: '法务部', role: '法务专员', drills: 7, rate: 8 },
  { name: '郑一帆', dept: '财务部', role: '财务总监', drills: 5, rate: 10 },
]

const trendChart: EChartsOption = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['中招人数', '财务类中招率%', 'HR类中招率%', '系统类中招率%'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 50, top: 34, bottom: 30 },
  xAxis: { type: 'category', data: ['3月', '4月', '5月', '6月', '7月', '8月'] },
  yAxis: [
    { type: 'value', name: '人数' },
    { type: 'value', name: '%', max: 40 },
  ],
  series: [
    { name: '中招人数', type: 'bar', barWidth: 22, data: [221, 198, 245, 310, 268, 187], itemStyle: { color: '#378ADD' } },
    { name: '财务类中招率%', type: 'line', yAxisIndex: 1, smooth: true, data: [38, 35, 40, 36, 33, 32], itemStyle: { color: '#D85A30' }, symbol: 'circle', symbolSize: 6 },
    { name: 'HR类中招率%', type: 'line', yAxisIndex: 1, smooth: true, data: [22, 20, 25, 23, 20, 17], itemStyle: { color: '#16A34A' }, symbol: 'circle', symbolSize: 6 },
    { name: '系统类中招率%', type: 'line', yAxisIndex: 1, smooth: true, data: [15, 13, 18, 14, 11, 9], itemStyle: { color: '#8E7CC3' }, symbol: 'circle', symbolSize: 6 },
  ],
}

const sceneRows = [
  { name: '财务报销钓鱼（仿 OA 登录页）', count: 6, rate: 36, comment: '中招率最高，建议高频演练' },
  { name: '工资条邮件钓鱼（伪装 HR）', count: 5, rate: 28, comment: '需加强附件安全意识培训' },
  { name: '系统升级通知（伪 IT 运维）', count: 5, rate: 19, comment: '整体意识良好，持续监控' },
  { name: '会议日程钓鱼（伪 Outlook）', count: 4, rate: 22, comment: '日历链接需警惕' },
  { name: '快递签收短信钓鱼', count: 3, rate: 16, comment: '短信渠道仍有漏洞' },
  { name: '供应商发票邮件（伪财务）', count: 4, rate: 31, comment: '财务人员重点关注' },
  { name: '招聘面试钓鱼（伪 HR 邀约）', count: 3, rate: 12, comment: '新员工培训效果显著' },
  { name: 'VPN 续费通知（伪 IT）', count: 3, rate: 9, comment: '技术人员意识较强' },
]

const selectedPerson = {
  name: '张小明',
  empId: 'EMP2023015',
  dept: '财务部',
  role: '会计',
  hireDate: '2023-03-15',
}

const radarChart: EChartsOption = {
  tooltip: {},
  legend: { data: ['张小明', '部门平均'], bottom: 0, textStyle: { fontSize: 11 } },
  radar: {
    indicator: [
      { name: '邮件识别', max: 100 },
      { name: '链接点击', max: 100 },
      { name: '密码提交', max: 100 },
      { name: '附件下载', max: 100 },
      { name: '举报意识', max: 100 },
    ],
    radius: 90,
  },
  series: [{
    type: 'radar',
    data: [
      {
        value: [58, 42, 35, 50, 28],
        name: '张小明',
        itemStyle: { color: '#D85A30' },
        areaStyle: { opacity: 0.25, color: '#D85A30' },
      },
      {
        value: [75, 70, 82, 78, 68],
        name: '部门平均',
        itemStyle: { color: '#378ADD' },
        areaStyle: { opacity: 0.2, color: '#378ADD' },
      },
    ],
  }],
}

// 个人风险值变化趋势（近6月）
const personRiskTrend: EChartsOption = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['个人风险值', '部门平均'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 20, top: 34, bottom: 30 },
  xAxis: { type: 'category', data: ['3月', '4月', '5月', '6月', '7月', '8月'] },
  yAxis: { type: 'value', name: '风险值', max: 100 },
  series: [
    { name: '个人风险值', type: 'line', smooth: true, data: [55, 62, 58, 70, 75, 68], itemStyle: { color: '#D85A30' }, areaStyle: { opacity: 0.12, color: '#D85A30' }, symbol: 'circle', symbolSize: 6 },
    { name: '部门平均', type: 'line', smooth: true, data: [48, 50, 47, 52, 50, 46], itemStyle: { color: '#378ADD' }, symbol: 'circle', symbolSize: 6 },
  ],
}

const timelineEvents = [
  { time: '2026-08-15', text: 'Q3全员演练：打开邮件 → 点击链接 → 输入密码（中招）', type: 'danger' as const, hollow: false },
  { time: '2026-07-20', text: '完成《钓鱼邮件识别进阶》培训，考试 72 分', type: 'warning' as const, hollow: true },
  { time: '2026-07-02', text: '财务专项演练：点击了链接（未输入密码）', type: 'warning' as const, hollow: false },
  { time: '2026-06-18', text: 'Q2全员演练：仅打开邮件，未点击', type: 'primary' as const, hollow: true },
  { time: '2026-05-10', text: '完成《信息安全基础》培训，考试 88 分', type: 'success' as const, hollow: true },
  { time: '2026-04-22', text: '新员工入职演练：首次中招，已推送培训', type: 'danger' as const, hollow: false },
]

const trainRows = [
  { course: '《信息安全基础规范》', date: '2026-04-08', score: 88 },
  { course: '《钓鱼邮件识别入门》', date: '2026-04-25', score: 82 },
  { course: '《企业数据安全红线》', date: '2026-05-10', score: 95 },
  { course: '《钓鱼邮件识别进阶》', date: '2026-07-20', score: 72 },
  { course: '《财务人员专项安全课》', date: '2026-08-02', score: 58 },
]
</script>

<style scoped lang="scss">
.chatbi-input :deep(.el-input-group__append) {
  padding: 0;
  .el-button { border: none; }
}
.trend-filter {
  display: flex;
  align-items: center;
}
.person-card {
  display: flex;
  align-items: center;
  gap: 16px;
}
.avatar-block {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  background: linear-gradient(135deg, #10B981, #059669);
  color: #fff;
  font-size: 28px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.person-info {
  flex: 1;
}
.person-name {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 6px;
}
.person-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.risk-score {
  display: flex;
  align-items: center;
  margin-top: 12px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.summary-big {
  font-size: 30px;
  font-weight: 600;
  color: var(--color-text-success);
  line-height: 1.2;
  &.danger { color: #dc2626; }
  &.info { color: var(--color-text-info); }
}
.summary-unit {
  font-size: 16px;
  font-weight: 400;
  margin-left: 2px;
  color: var(--color-text-tertiary);
}
.summary-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 8px;
  line-height: 1.5;
}
</style>
