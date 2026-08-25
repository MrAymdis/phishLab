<template>
  <div class="page-container">
    <PageHeader title="数据报表">
      <template #actions>
        <el-button size="small" :icon="Refresh">刷新数据</el-button>
        <div class="chatbi-input">
          <el-input v-model="chatbiQuery" size="small" placeholder="自然语言问数，如:上月财务部中招率" style="width: 320px"
            @keyup.enter="askChatbi">
            <template #append>
              <el-button type="primary" :icon="Promotion" :loading="chatbiLoading" @click="askChatbi">发送</el-button>
            </template>
          </el-input>
        </div>
        <el-button size="small" :icon="Document" :loading="exporting" @click="doExport('pdf')">导出 PDF</el-button>
        <el-button size="small" :icon="DocumentCopy" :loading="exporting" @click="doExport('excel')">导出 Excel</el-button>
      </template>
    </PageHeader>

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
            <pre class="chatbi-sql">{{ chatbiResult.sql }}</pre>
          </el-collapse-item>
        </el-collapse>
      </template>
    </el-dialog>

    <el-tabs v-model="activeTab" style="margin: 8px 16px 0">
      <el-tab-pane label="演练报表" name="drill">
        <el-row :gutter="12" align="stretch" style="margin: 16px 0 0">
          <el-col :span="8">
            <div class="card card-blue" style="height: 100%">
              <div class="card-title">选择演练</div>
              <el-select v-model="selectedDrill" size="default" style="width: 100%; margin-top: 8px" @change="loadDrillReport">
                <el-option v-for="c in drillOptions" :key="c.id" :label="c.label" :value="c.id" />
              </el-select>
            </div>
          </el-col>
          <el-col :span="8">
            <StatCard title="综合得分" :value="drillScore" suffix=" 分" sub="100 - 中招率×2" accent="teal" />
          </el-col>
          <el-col :span="8">
            <StatCard title="覆盖部门" :value="drillDeptCount" suffix=" 个" accent="purple" />
          </el-col>
        </el-row>

        <!-- 核心行为指标 -->
        <el-row :gutter="12" align="stretch" style="margin: 12px 0 0">
          <el-col :span="6" v-for="m in drillMetrics" :key="m.title">
            <StatCard :title="m.title" :value="m.value" :suffix="m.suffix" :sub="m.sub" :accent="m.accent" />
          </el-col>
        </el-row>

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 0">
          <el-col :span="12">
            <div class="card card-orange" style="height: 100%">
              <div class="card-title">转化漏斗分析</div>
              <FunnelChart :items="drillFunnel" height="320px" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-blue" style="height: 100%">
              <div class="card-title">演练期间每日趋势</div>
              <BaseChart :option="dailyTrendChart" height="320px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-purple" style="height: 100%">
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

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-red" style="height: 100%">
              <div class="card-title">中招明细</div>
              <el-table :data="pagedVictims" size="small" style="margin-top: 8px">
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
                <el-table-column label="运行附件" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.run_attach" type="danger" size="small">是</el-tag>
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
                v-if="victimRows.length > 10"
                v-model:current-page="victimPage"
                v-model:page-size="victimPageSize"
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, sizes, prev, pager, next"
                :total="victimRows.length"
                :page-sizes="[10, 20, 50, 100]"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="部门报表" name="dept">
        <!-- 时间范围筛选 -->
        <el-row :gutter="12" align="stretch" style="margin: 16px 0 0">
          <el-col :span="24">
            <div class="card card-blue" style="height: 100%">
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

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 0">
          <el-col :span="12">
            <div class="card card-purple" style="height: 100%">
              <div class="card-title">各部门安全意识横向对比（中招率%）</div>
              <BaseChart :option="deptBarChart" height="420px" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-green" style="height: 100%">
              <div class="card-title">
                <el-select v-model="selectedDept" size="small" style="width: 180px" @change="loadDeptPersons">
                  <el-option label="全部部门" :value="0" />
                  <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
                </el-select>
                <span style="margin-left: 8px">人员明细</span>
              </div>
              <el-empty v-if="!selectedDept" description="请选择具体部门查看人员明细" :image-size="60" style="padding: 16px 0" />
              <template v-else>
                <el-table :data="deptPersonRows" size="small" style="margin-top: 8px">
                  <el-table-column label="姓名" prop="name" width="80" />
                  <el-table-column label="工号" prop="empNo" width="90" />
                  <el-table-column label="部门" prop="dept" width="100" />
                  <el-table-column label="岗位" prop="position" min-width="100" />
                  <el-table-column label="参与次数" prop="drills" width="80" align="center" />
                  <el-table-column label="中招率" width="90" align="center">
                    <template #default="{ row }">{{ row.victimRate }}%</template>
                  </el-table-column>
                  <el-table-column label="风险" width="70" align="center">
                    <template #default="{ row }">
                      <el-tag v-if="row.risk === 'high'" type="danger" size="small">高</el-tag>
                      <el-tag v-else-if="row.risk === 'mid'" type="warning" size="small">中</el-tag>
                      <el-tag v-else type="success" size="small">低</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="!deptPersonRows.length" description="该部门暂无投递记录" :image-size="60" style="padding: 16px 0" />
              </template>
            </div>
          </el-col>
        </el-row>

        <!-- 部门维度明细表 -->
        <el-row :gutter="12" align="stretch" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-teal" style="height: 100%">
              <div class="card-title">部门维度明细</div>
              <el-table :data="deptDetailRows" size="small" style="margin-top: 8px">
                <el-table-column label="部门" prop="dept" min-width="140" />
                <el-table-column label="总人数" prop="total" width="90" align="center" />
                <el-table-column label="覆盖次数" prop="targetCount" width="90" align="center" />
                <el-table-column label="中招次数" prop="victim" width="90" align="center" />
                <el-table-column label="平均中招率" width="110" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.submitRate >= 25 ? '#dc2626' : row.submitRate >= 15 ? '#d97706' : '#16a34a', fontWeight: 600 }">
                      {{ row.submitRate }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="举报数" prop="report" width="90" align="center" />
                <el-table-column label="培训完成率" width="110" align="center">
                  <template #default="{ row }">{{ row.trainRate }}%</template>
                </el-table-column>
                <el-table-column label="风险评级" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.submitRate >= 25" type="danger" size="small">高风险</el-tag>
                    <el-tag v-else-if="row.submitRate >= 15" type="warning" size="small">中风险</el-tag>
                    <el-tag v-else type="success" size="small">低风险</el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!deptDetailRows.length" description="统计周期内暂无部门投递数据" :image-size="60" style="padding: 16px 0" />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="综合趋势" name="trend">
        <el-row :gutter="12" align="stretch" style="margin: 16px 0 0">
          <el-col :span="24">
            <div class="card card-teal" style="height: 100%">
              <div class="card-title">
                <div class="trend-filter">
                  <el-radio-group v-model="trendRange" size="small">
                    <el-radio-button value="3m">近3月</el-radio-button>
                    <el-radio-button value="6m">近半年</el-radio-button>
                    <el-radio-button value="1y">近一年</el-radio-button>
                  </el-radio-group>
                  <el-checkbox-group v-model="sceneCheck" size="small" style="margin-left: 20px">
                    <el-checkbox v-for="s in sceneTypes" :key="s" :value="s">{{ s }}</el-checkbox>
                  </el-checkbox-group>
                </div>
              </div>
              <BaseChart :option="trendChart" height="340px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-blue" style="height: 100%">
              <div class="card-title">场景防范意识表</div>
              <el-table :data="filteredScenes" size="small" style="margin-top: 8px">
                <el-table-column label="场景名称" prop="name" min-width="160" />
                <el-table-column label="演练次数" prop="count" width="100" align="center" />
                <el-table-column label="平均中招率" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.rate >= 25 ? 'danger' : row.rate >= 15 ? 'warning' : 'success'" size="small" effect="plain">
                      {{ row.rate }}%
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="举报率" width="110" align="center">
                  <template #default="{ row }">{{ row.reportRate }}%</template>
                </el-table-column>
                <el-table-column label="整体评价" min-width="200">
                  <template #default="{ row }">
                    <el-tag v-if="row.rate >= 25" type="danger" size="small">需重点培训</el-tag>
                    <el-tag v-else-if="row.rate >= 15" type="warning" size="small">需持续关注</el-tag>
                    <el-tag v-else type="success" size="small">意识良好</el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!filteredScenes.length" description="统计周期内暂无演练数据" :image-size="60" style="padding: 16px 0" />
            </div>
          </el-col>
        </el-row>

        <!-- 趋势总结卡片 -->
        <el-row :gutter="12" align="stretch" style="margin: 12px 0 16px">
          <el-col :span="8">
            <div class="card card-green" style="height: 100%">
              <div class="card-title">安全意识提升率</div>
              <div class="summary-big">{{ trendImprovement }}<span class="summary-unit">%</span></div>
              <div class="summary-desc">{{ trendImprovementDesc }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="card card-red" style="height: 100%">
              <div class="card-title">最薄弱场景</div>
              <div class="summary-big danger">{{ weakestScene }}</div>
              <div class="summary-desc">{{ weakestSceneDesc }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="card card-blue" style="height: 100%">
              <div class="card-title">意识最佳部门</div>
              <div class="summary-big info">{{ bestDept }}</div>
              <div class="summary-desc">{{ bestDeptDesc }}</div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="员工个人报表" name="person">
        <el-row :gutter="12" align="stretch" style="margin: 16px 0 0">
          <el-col :span="8">
            <div class="card card-blue" style="height: 100%">
              <div class="card-title">搜索员工</div>
              <el-select
                v-model="selectedPersonId"
                filterable
                remote
                clearable
                :remote-method="searchPersons"
                :loading="personLoading"
                placeholder="输入姓名 / 工号搜索"
                style="width: 100%; margin-top: 8px"
                @change="loadPersonal"
              >
                <el-option v-for="u in personCandidates" :key="u.id" :label="u.label" :value="u.id" />
              </el-select>
            </div>
          </el-col>
          <el-col :span="16">
            <div class="card card-teal" style="height: 100%">
              <div class="person-card">
                <div class="avatar-block">{{ (selectedPerson.name || '?').slice(0, 1) }}</div>
                <div class="person-info">
                  <div class="person-name">{{ selectedPerson.name || '未选择员工' }}</div>
                  <div class="person-meta">
                    <span v-if="selectedPerson.empNo">工号：{{ selectedPerson.empNo }}</span>
                    <span v-if="selectedPerson.dept">部门：{{ selectedPerson.dept }}</span>
                    <span v-if="selectedPerson.position">岗位：{{ selectedPerson.position }}</span>
                    <span v-if="selectedPerson.email">邮箱：{{ selectedPerson.email }}</span>
                  </div>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 0">
          <el-col :span="12">
            <div class="card card-orange" style="height: 100%">
              <div class="card-title">五维能力雷达（个人风险画像）</div>
              <BaseChart :option="radarChart" height="300px" />
              <div class="risk-score">
                <span style="margin-right: 12px">个人风险值总分：</span>
                <el-progress :percentage="personRiskTotal" :stroke-width="14" color="#D85A30" style="flex: 1" />
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-purple" style="height: 100%">
              <div class="card-title">历史行为轨迹</div>
              <el-timeline class="behavior-timeline" style="margin-top: 4px">
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
        <el-row :gutter="12" align="stretch" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-red" style="height: 100%">
              <div class="card-title">个人风险值变化趋势（近6月）</div>
              <BaseChart v-if="personRiskTrendHasData" :option="personRiskTrend" height="240px" />
              <el-empty v-else description="风险历史暂未归档（画像按周期归档二期提供）" :image-size="70" style="padding: 24px 0" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" align="stretch" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-green" style="height: 100%">
              <div class="card-title">培训完成记录</div>
              <el-table :data="trainRows" size="small" style="margin-top: 8px">
                <el-table-column label="课程名称" prop="course" min-width="200" />
                <el-table-column label="完成日期" prop="date" width="130" />
                <el-table-column label="进度" width="100" align="center">
                  <template #default="{ row }">{{ row.progress }}%</template>
                </el-table-column>
                <el-table-column label="状态" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.status === '已完成' ? 'success' : row.status === '学习中' ? 'primary' : 'info'" size="small">
                      {{ row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!trainRows.length" description="暂无培训记录" :image-size="60" style="padding: 16px 0" />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import { Refresh, Promotion, Document, DocumentCopy } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import BaseChart from '@/components/base/BaseChart.vue'
import FunnelChart from '@/components/business/FunnelChart.vue'
import { analyticsApi, campaignApi, orgApi, aiApi, type ChatbiResult } from '@/api'

const activeTab = ref('drill')
const chatbiQuery = ref('')
const chatbiLoading = ref(false)
const chatbiVisible = ref(false)
const chatbiResult = shallowRef<ChatbiResult | null>(null)

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

/** ChatBI 问数：只读查询 + 数据权限注入 + 审计（红线 5） */
async function askChatbi() {
  const q = chatbiQuery.value.trim()
  if (!q) { ElMessage.warning('请输入要查询的问题'); return }
  chatbiLoading.value = true
  try {
    chatbiResult.value = await aiApi.chatbi(q)
    chatbiVisible.value = true
  } catch {
    /* 错误已由 http 层提示 */
  } finally {
    chatbiLoading.value = false
  }
}
const deptRange = ref('month')
const trendRange = ref('3m')
const sceneCheck = ref<string[]>([])
const exporting = ref(false)

/** 按当前 tab 收集参数导出 PDF/Excel（文件流下载）。 */
async function doExport(kind: 'excel' | 'pdf') {
  const payload: Record<string, unknown> = { kind, range: deptRange.value }
  const tab = activeTab.value
  if (tab === 'drill') {
    if (!selectedDrill.value) { ElMessage.warning('请先在「演练报表」选择演练'); return }
    payload.scope = 'campaign'
    payload.campaign_id = selectedDrill.value
  } else if (tab === 'dept') {
    payload.scope = 'department'
    if (selectedDept.value && selectedDept.value !== 0) payload.dept_id = selectedDept.value
  } else if (tab === 'trend') {
    payload.scope = 'trend'
    payload.range = trendRangeMap[trendRange.value] ?? 'month'
  } else if (tab === 'person') {
    if (!selectedPersonId.value) { ElMessage.warning('请先搜索并选择员工'); return }
    payload.scope = 'personal'
    payload.user_id = selectedPersonId.value
  } else {
    ElMessage.warning('当前报表范围不支持导出'); return
  }
  exporting.value = true
  try {
    await analyticsApi.exportReport(payload as never)
    ElMessage.success('导出成功，文件已开始下载')
  } catch { /* 错误提示已在 http 层处理 */ }
  finally { exporting.value = false }
}

// ============ 演练报表（真实数据 GET /api/v1/reports/campaign/{id}） ============
const selectedDrill = ref<number | null>(null)
const drillOptions = ref<{ id: number; label: string }[]>([])
const drillScore = ref('--')
const drillDeptCount = ref(0)
const victimPage = ref(1)
const victimPageSize = ref(10)

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const drillMetrics = ref<{ title: string; value: string | number; suffix: string; sub: string; accent: Accent }[]>([])
const drillFunnel = ref<{ name: string; value: number; rate: string }[]>([])
const deptCompareRows = ref<{ dept: string; sent: number; victim: number; victimRate: number; report: number; reportRate: number }[]>([])
const victimRows = ref<{ name: string; dept: string; email: string; first_open: string; clicks: number; input_pwd: boolean; risk: string }[]>([])

const pagedVictims = computed(() =>
  victimRows.value.slice((victimPage.value - 1) * victimPageSize.value, victimPage.value * victimPageSize.value),
)

const dailyTrendChart = shallowRef<EChartsOption>({
  tooltip: { trigger: 'axis' },
  legend: { data: ['打开', '点击', '中招'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 20, top: 34, bottom: 30 },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [
    { name: '打开', type: 'line', smooth: true, data: [], itemStyle: { color: '#378ADD' }, areaStyle: { opacity: 0.08 } },
    { name: '点击', type: 'line', smooth: true, data: [], itemStyle: { color: '#D85A30' } },
    { name: '中招', type: 'line', smooth: true, data: [], itemStyle: { color: '#A32D2D' } },
  ],
})

async function loadDrills() {
  try {
    const res = (await campaignApi.list({ page: 1, pageSize: 100 })) as { list: { id: number; name: string }[] }
    drillOptions.value = (res?.list ?? []).map(c => ({ id: c.id, label: `#${c.id} ${c.name}` }))
    if (drillOptions.value.length) {
      selectedDrill.value = selectedDrill.value ?? drillOptions.value[0].id
      loadDrillReport()
    }
  } catch { /* 演练列表加载失败：下拉为空态 */ }
}

async function loadDrillReport() {
  if (!selectedDrill.value) return
  try {
    const data = (await analyticsApi.campaignReport(selectedDrill.value)) as Record<string, any>
    const metrics: any[] = data?.metrics ?? []
    // 综合得分已在顶部卡片展示，指标行去掉打开数（与漏斗/趋势重复）
    drillMetrics.value = metrics.slice(0, 5)
      .filter((m: any) => m.title !== '打开数')
      .map((m: any) => ({
        ...m,
        value: typeof m.value === 'number' ? m.value.toLocaleString() : m.value,
      }))
    drillScore.value = metrics[5]?.value ?? '--'
    drillFunnel.value = (data?.funnel ?? []).map((f: any) => ({
      ...f,
      // rate 为 null：上一级计数为 0（如客户端屏蔽图片导致打开缺失），显示 -- 而非 0.0%
      rate: typeof f.rate === 'number' ? `${f.rate}%` : (f.rate ?? '--'),
    }))
    const victims: any[] = data?.victims ?? []
    // 后端无 risk 字段，按行为推导：输入密码 / 运行附件均为高危中招，点击 2 次以上中危
    victimRows.value = victims.map((v: any) => ({
      ...v,
      risk: v.input_pwd || v.run_attach ? 'high' : v.clicks >= 2 ? 'mid' : 'low',
    }))
    deptCompareRows.value = data?.deptCompare ?? []
    drillDeptCount.value = deptCompareRows.value.length
    if (data?.dailyTrend?.labels) {
      const dt = data.dailyTrend
      const series = dailyTrendChart.value.series as any[]
      dailyTrendChart.value = {
        ...dailyTrendChart.value,
        xAxis: { ...(dailyTrendChart.value.xAxis as any), data: dt.labels },
        series: series.map((s, i) => ({ ...s, data: [dt.opens, dt.clicks, dt.submits][i] ?? [] })),
      }
    }
    victimPage.value = 1
  } catch {
    ElMessage.warning('演练报表加载失败，请检查网络或后端服务')
  }
}

// ============ 部门报表（真实数据 GET /api/v1/reports/department） ============
const selectedDept = ref(0)
const deptOptions = ref<{ id: number; name: string }[]>([])
const deptDetailRows = ref<any[]>([])
const deptPersonRows = ref<any[]>([])

const deptBarChart = shallowRef<EChartsOption>({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 90, right: 40, top: 20, bottom: 30 },
  // max 自适应数据：中招率可超 40%（如部门 56%），固定 40 会截断柱子
  xAxis: { type: 'value', name: '中招率%', max: (v: any) => Math.max(40, Math.ceil((v.max || 0) * 1.1)) },
  yAxis: { type: 'category', data: [] },
  series: [{
    type: 'bar', barWidth: 22, data: [],
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
})

function flattenDepts(nodes: any[]): { id: number; name: string }[] {
  const out: { id: number; name: string }[] = []
  const walk = (ns: any[]) => ns.forEach((n) => {
    out.push({ id: n.id, name: n.name })
    if (n.children?.length) walk(n.children)
  })
  walk(nodes)
  return out
}

async function loadDepts() {
  try {
    const tree = (await orgApi.deptTree()) as any[]
    deptOptions.value = flattenDepts(tree ?? [])
  } catch { /* 部门树加载失败 */ }
}

async function loadDepartment() {
  try {
    const data = (await analyticsApi.department(deptRange.value)) as Record<string, any>
    deptDetailRows.value = data?.rows ?? []
    if (Array.isArray(data?.labels) && Array.isArray(data?.submitRates)) {
      deptBarChart.value = {
        ...deptBarChart.value,
        yAxis: { ...(deptBarChart.value.yAxis as any), data: data.labels },
        series: [{ ...(deptBarChart.value.series as any)[0], data: data.submitRates }],
      }
    }
  } catch {
    ElMessage.warning('部门报表加载失败，请检查网络或后端服务')
  }
}

async function loadDeptPersons() {
  deptPersonRows.value = []
  if (!selectedDept.value) return
  try {
    const data = (await analyticsApi.deptPersons(selectedDept.value, deptRange.value)) as Record<string, any>
    deptPersonRows.value = data?.rows ?? []
  } catch {
    ElMessage.warning('人员明细加载失败，请检查网络或后端服务')
  }
}

// ============ 综合趋势（真实数据 GET /api/v1/reports/trend） ============
const trendRangeMap: Record<string, string> = { '3m': 'month', '6m': 'quarter', '1y': 'year' }
const sceneRows = ref<any[]>([])
const sceneTypes = computed(() => [...new Set(sceneRows.value.map(s => s.name))])
const filteredScenes = computed(() =>
  sceneCheck.value.length ? sceneRows.value.filter(s => sceneCheck.value.includes(s.name)) : sceneRows.value,
)

const trendChart = shallowRef<EChartsOption>({
  tooltip: { trigger: 'axis' },
  legend: { data: ['演练次数', '中招率%', '举报率%'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 50, top: 34, bottom: 30 },
  xAxis: { type: 'category', data: [] },
  yAxis: [
    { type: 'value', name: '次数' },
    // max 自适应：中招率超 40% 时不被截断
    { type: 'value', name: '%', max: (v: any) => Math.max(40, Math.ceil((v.max || 0) * 1.1)) },
  ],
  series: [
    { name: '演练次数', type: 'bar', barWidth: 22, data: [], itemStyle: { color: '#378ADD' } },
    { name: '中招率%', type: 'line', yAxisIndex: 1, smooth: true, data: [], itemStyle: { color: '#D85A30' }, symbol: 'circle', symbolSize: 6 },
    { name: '举报率%', type: 'line', yAxisIndex: 1, smooth: true, data: [], itemStyle: { color: '#16A34A' }, symbol: 'circle', symbolSize: 6 },
  ],
})

const trendImprovement = ref('--')
const trendImprovementDesc = ref('统计周期内暂无足够数据对比')
const weakestScene = ref('--')
const weakestSceneDesc = ref('')
const bestDept = ref('--')
const bestDeptDesc = ref('')

async function loadTrend() {
  try {
    const [data, deptData] = await Promise.all([
      analyticsApi.trend(trendRangeMap[trendRange.value] ?? 'month'),
      analyticsApi.department(trendRangeMap[trendRange.value] ?? 'month'),
    ]) as [Record<string, any>, Record<string, any>]
    if (Array.isArray(data?.labels) && data.labels.length) {
      const series = trendChart.value.series as any[]
      trendChart.value = {
        ...trendChart.value,
        xAxis: { ...(trendChart.value.xAxis as any), data: data.labels },
        series: [
          { ...series[0], data: data.campaignCounts ?? [] },
          { ...series[1], data: data.submitRates ?? [] },
          { ...series[2], data: data.reportRates ?? [] },
        ],
      }
      const rates: number[] = data.submitRates ?? []
      if (rates.length >= 2 && (rates[0] > 0 || rates[rates.length - 1] > 0)) {
        const first = rates.find((r) => r > 0) ?? rates[0]
        const last = rates[rates.length - 1]
        const drop = Math.round((1 - last / first) * 100)
        trendImprovement.value = String(drop)
        trendImprovementDesc.value = `中招率由 ${first}% 降至 ${last}%，整体安全意识${drop >= 0 ? '提升' : '下降'}`
      }
    }
    sceneRows.value = (data?.scenes ?? []).map((s: any) => ({
      name: s.scene, count: s.targetCount ?? 0,
      rate: s.submitRate ?? 0, reportRate: s.reportRate ?? 0,
    }))
    if (sceneRows.value.length) {
      const worst = [...sceneRows.value].sort((a, b) => b.rate - a.rate)[0]
      weakestScene.value = worst.name
      weakestSceneDesc.value = `平均中招率 ${worst.rate}%，建议对该场景开展专项演练`
    }
    const deptRows: any[] = deptData?.rows ?? []
    if (deptRows.length) {
      const best = [...deptRows].sort((a, b) => a.submitRate - b.submitRate)[0]
      bestDept.value = best.dept
      bestDeptDesc.value = `平均中招率 ${best.submitRate}%（${deptRows.length} 个部门中最低）`
    }
  } catch {
    ElMessage.warning('综合趋势加载失败，请检查网络或后端服务')
  }
}

// ============ 员工个人报表（真实数据 GET /api/v1/reports/personal/{uid}） ============
const selectedPersonId = ref<number | null>(null)
const personCandidates = ref<any[]>([])
const personLoading = ref(false)
const selectedPerson = ref({ name: '', empNo: '', dept: '', position: '', email: '' })
const personRiskTotal = ref(0)
const personRiskTrendHasData = ref(false)

const radarChart = shallowRef<EChartsOption>({
  tooltip: {},
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
    data: [{ value: [0, 0, 0, 0, 0], name: '个人', itemStyle: { color: '#D85A30' }, areaStyle: { opacity: 0.25, color: '#D85A30' } }],
  }],
})

const personRiskTrend = shallowRef<EChartsOption>({
  tooltip: { trigger: 'axis' },
  legend: { data: ['个人风险值'], textStyle: { fontSize: 11 }, top: 0 },
  grid: { left: 40, right: 20, top: 34, bottom: 30 },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value', name: '风险值', max: 100 },
  series: [{ name: '个人风险值', type: 'line', smooth: true, data: [], itemStyle: { color: '#D85A30' }, areaStyle: { opacity: 0.12, color: '#D85A30' }, symbol: 'circle', symbolSize: 6 }],
})

type TimelineType = 'primary' | 'success' | 'warning' | 'danger' | 'info'
const timelineEvents = ref<{ time: string; text: string; type: TimelineType; hollow: boolean }[]>([])
const trainRows = ref<{ course: string; date: string; progress: number; status: string }[]>([])

async function searchPersons(kw: string) {
  if (!kw) {
    personCandidates.value = []
    return
  }
  personLoading.value = true
  try {
    const res = (await orgApi.users({ kw, page: 1, pageSize: 20 })) as { list: any[] }
    personCandidates.value = (res?.list ?? []).map(u => ({
      id: u.id,
      label: `${u.name}（${u.no || u.email}）`,
      name: u.name, empNo: u.no, dept: u.deptShort, position: u.pos, email: u.email,
    }))
  } catch {
    personCandidates.value = []
  } finally {
    personLoading.value = false
  }
}

async function loadPersonal() {
  if (!selectedPersonId.value) return
  const cand = personCandidates.value.find(c => c.id === selectedPersonId.value)
  if (cand) selectedPerson.value = { name: cand.name, empNo: cand.empNo, dept: cand.dept, position: cand.position, email: cand.email }
  try {
    const data = (await analyticsApi.personal(selectedPersonId.value)) as Record<string, any>
    if (Array.isArray(data?.profile?.dims) && data.profile.dims.length) {
      const dims = data.profile.dims
      const series = radarChart.value.series as any[]
      radarChart.value = {
        ...radarChart.value,
        radar: { ...(radarChart.value.radar as any), indicator: dims.map((d: any) => ({ name: d.label, max: 100 })) },
        series: [{ ...series[0], data: [{ ...series[0].data[0], value: dims.map((d: any) => d.val) }] }],
      }
      personRiskTotal.value = data.profile.total ?? 0
    }
    personRiskTrendHasData.value = Array.isArray(data?.trend?.labels) && data.trend.labels.length > 0
    if (personRiskTrendHasData.value) {
      personRiskTrend.value = {
        ...personRiskTrend.value,
        xAxis: { ...(personRiskTrend.value.xAxis as any), data: data.trend.labels },
        series: [{ ...(personRiskTrend.value.series as any)[0], data: data.trend.scores ?? [] }],
      }
    }
    const eventColor: Record<string, TimelineType> = { open: 'primary', click: 'warning', submit: 'danger', attach_run: 'danger', report: 'success', bounce: 'info' }
    timelineEvents.value = (data?.timeline ?? []).map((t: any) => ({
      time: t.time,
      text: t.desc ? `${t.title}：${t.desc}` : t.title,
      type: eventColor[t.type] ?? 'primary',
      hollow: false,
    }))
    trainRows.value = (data?.trainings ?? []).map((t: any) => ({
      course: t.name, date: t.completedAt ?? '', progress: t.progress ?? 0, status: t.status ?? '',
    }))
  } catch {
    ElMessage.warning('个人报表加载失败，请检查网络或后端服务')
  }
}

// ============ 加载时机（Tab 首次激活才加载对应数据） ============
const loadedTabs = ref<Record<string, boolean>>({})
function ensureTabLoaded(tab: string) {
  if (loadedTabs.value[tab]) return
  loadedTabs.value[tab] = true
  if (tab === 'drill') { loadDrills() }
  else if (tab === 'dept') { loadDepts(); loadDepartment() }
  else if (tab === 'trend') loadTrend()
  else if (tab === 'person') loadPersonal()
}

watch(activeTab, (tab) => ensureTabLoaded(tab))
watch(deptRange, () => { if (loadedTabs.value.dept) { loadDepartment(); loadDeptPersons() } })
watch(trendRange, () => { if (loadedTabs.value.trend) loadTrend() })

onMounted(() => ensureTabLoaded(activeTab.value))
</script>

<style scoped lang="scss">
.chatbi-sql {
  margin: 0;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
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
/* 历史行为轨迹时间轴：与并排雷达图等高，超出滚动 */
.behavior-timeline {
  max-height: 300px;
  overflow-y: auto;
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
