<template>
  <div class="page-container">
    <PageHeader title="邮件举报">
      <template #actions>
        <el-button size="small" :icon="Download">下载 Outlook 插件</el-button>
        <el-button size="small" :icon="Picture">下载 Web 邮箱按钮</el-button>
        <el-button size="small" :icon="Setting">API 配置说明</el-button>
        <el-button size="small" :icon="Refresh">刷新</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" style="margin: 8px 16px 0">
      <el-tab-pane label="举报插件管理" name="plugin">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="12">
            <div class="card card-blue plugin-card">
              <div class="plugin-header">
                <div class="plugin-icon outlook-icon">📧</div>
                <div class="plugin-title-wrap">
                  <div class="plugin-title">Outlook 桌面客户端插件</div>
                  <div class="plugin-sub">支持一键举报可疑邮件到安全运营中心</div>
                </div>
                <el-button type="primary" :icon="Download">下载</el-button>
              </div>
              <el-descriptions :column="2" size="small" border style="margin-top: 12px">
                <el-descriptions-item label="版本号">v2.4.1</el-descriptions-item>
                <el-descriptions-item label="更新日期">2026-08-01</el-descriptions-item>
                <el-descriptions-item label="下载次数">2,860 次</el-descriptions-item>
                <el-descriptions-item label="SHA256">8f3a...c29d</el-descriptions-item>
              </el-descriptions>
              <div class="plugin-section">
                <div class="section-title">安装指引</div>
                <ol class="step-list">
                  <li>关闭所有 Outlook 窗口</li>
                  <li>双击运行 <code>PhishLab-Outlook-v2.4.1.msi</code></li>
                  <li>按向导完成安装，重启 Outlook</li>
                  <li>在 Outlook 功能区会出现「一键举报」按钮</li>
                  <li>首次使用输入企业域名完成激活</li>
                </ol>
              </div>
              <div class="plugin-section">
                <div class="section-title">支持的邮箱客户端</div>
                <div class="tag-list">
                  <el-tag size="small">Outlook 2016+（Windows）</el-tag>
                  <el-tag size="small">Outlook 2019+（Mac）</el-tag>
                  <el-tag size="small">Outlook 365 桌面版</el-tag>
                </div>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-green plugin-card">
              <div class="plugin-header">
                <div class="plugin-icon webmail-icon">🌐</div>
                <div class="plugin-title-wrap">
                  <div class="plugin-title">Web 邮箱举报按钮</div>
                  <div class="plugin-sub">通过浏览器书签/扩展在网页版邮箱举报</div>
                </div>
                <el-button type="primary" :icon="Picture">下载</el-button>
              </div>
              <el-descriptions :column="2" size="small" border style="margin-top: 12px">
                <el-descriptions-item label="版本号">v1.8.0</el-descriptions-item>
                <el-descriptions-item label="更新日期">2026-07-20</el-descriptions-item>
                <el-descriptions-item label="安装次数">1,240 次</el-descriptions-item>
                <el-descriptions-item label="支持浏览器">Chrome / Edge / Firefox</el-descriptions-item>
              </el-descriptions>
              <div class="plugin-section">
                <div class="section-title">安装指引</div>
                <ol class="step-list">
                  <li>将「一键举报」按钮拖拽到浏览器书签栏</li>
                  <li>或下载对应的浏览器扩展包（crx/xpi）</li>
                  <li>在扩展管理页开启开发者模式并加载</li>
                  <li>登录 Web 邮箱，打开邮件后点击按钮即可举报</li>
                </ol>
              </div>
              <div class="plugin-section">
                <div class="section-title">支持的邮箱客户端</div>
                <div class="tag-list">
                  <el-tag size="small">企业微信邮箱</el-tag>
                  <el-tag size="small">钉钉邮箱</el-tag>
                  <el-tag size="small">飞书邮箱</el-tag>
                  <el-tag size="small">Outlook Web</el-tag>
                  <el-tag size="small">腾讯企业邮</el-tag>
                  <el-tag size="small">网易企业邮</el-tag>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-purple">
              <div class="card-title">举报 API 配置</div>
              <el-form label-width="140px" style="margin-top: 8px; max-width: 720px">
                <el-form-item label="API Endpoint">
                  <el-input v-model="apiConfig.endpoint" readonly>
                    <template #append>
                      <el-button :icon="CopyDocument">复制</el-button>
                    </template>
                  </el-input>
                </el-form-item>
                <el-form-item label="Webhook URL">
                  <el-input v-model="apiConfig.webhook" readonly>
                    <template #append>
                      <el-button :icon="CopyDocument">复制</el-button>
                    </template>
                  </el-input>
                </el-form-item>
                <el-form-item label="认证 Token">
                  <el-input v-model="apiConfig.token" type="password" show-password readonly>
                    <template #append>
                      <el-button :icon="RefreshRight" @click="regenerateToken">重生成</el-button>
                      <el-button :icon="CopyDocument">复制</el-button>
                    </template>
                  </el-input>
                </el-form-item>
              </el-form>
              <div class="code-section">
                <div class="section-title">
                  接入代码示例（cURL）
                  <el-button size="small" link type="primary" :icon="CopyDocument">复制代码</el-button>
                </div>
                <pre class="code-block"><code>curl -X POST https://api.phishlab.example.com/v1/reports/mail \
  -H "Authorization: Bearer {{ apiConfig.token }}" \
  -H "Content-Type: application/json" \
  -d '{
    "reporter_email": "zhangsan@example.com",
    "subject": "【紧急】工资条更新通知",
    "sender": "hr-department@phishing.com",
    "raw_mail_base64": "..."
  }'

# 响应示例：
# {
#   "report_id": "RPT202608160001",
#   "auto_classification": "phishing_real",
#   "confidence": 0.94
# }</code></pre>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="举报中心" name="center">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="24">
            <div class="card card-blue">
              <div class="toolbar">
                <el-date-picker
                  v-model="reportDateRange"
                  type="daterange"
                  size="small"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                />
                <el-select v-model="reportCategory" size="small" placeholder="全部分类" style="width: 160px">
                  <el-option label="全部" value="" />
                  <el-option label="演练钓鱼" value="drill" />
                  <el-option label="真实钓鱼" value="real" />
                  <el-option label="误报" value="false" />
                </el-select>
                <el-input v-model="reportKw" size="small" placeholder="搜索主题/发件人/举报人" style="width: 280px" clearable />
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="6"><StatCard title="累计举报量" value="3,428" suffix=" 封" accent="blue" /></el-col>
          <el-col :span="6"><StatCard title="本月举报" value="486" suffix=" 封" accent="teal" /></el-col>
          <el-col :span="6"><StatCard title="真实钓鱼数" value="62" suffix=" 封" accent="red" /></el-col>
          <el-col :span="6"><StatCard title="误报率" value="18.3" suffix=" %" accent="orange" /></el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-teal">
              <div class="card-title">举报记录</div>
              <el-table :data="reportRows" size="small" style="margin-top: 8px">
                <el-table-column label="时间" prop="time" width="160" />
                <el-table-column label="邮件主题" prop="subject" min-width="220" show-overflow-tooltip />
                <el-table-column label="发件人" prop="sender" min-width="180" show-overflow-tooltip />
                <el-table-column label="举报人" width="160">
                  <template #default="{ row }">
                    <div>
                      <div>{{ row.reporter }}</div>
                      <div style="font-size: 11px; color: var(--color-text-tertiary)">{{ row.reporterDept }}</div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="自动分类结果" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.auto === 'drill'" type="primary" size="small">演练钓鱼</el-tag>
                    <el-tag v-else-if="row.auto === 'real'" type="danger" size="small">真实钓鱼</el-tag>
                    <el-tag v-else type="info" size="small">误报</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="人工复核结果" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.manual === 'real'" type="danger" size="small">真实钓鱼</el-tag>
                    <el-tag v-else-if="row.manual === 'false'" type="info" size="small">误报</el-tag>
                    <el-tag v-else-if="row.manual === 'drill'" type="primary" size="small">演练</el-tag>
                    <span v-else style="color: var(--color-text-tertiary); font-size: 12px">待复核</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="280" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" type="primary" @click="openDetailDialog(row)">详情</el-button>
                    <el-button link size="small" type="danger" @click="openRealDialog(row)" v-if="!row.manual">研判为真实钓鱼</el-button>
                    <el-button link size="small" v-if="!row.manual">标记误报</el-button>
                    <el-button link size="small" type="success">推送SOC</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-pagination
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, sizes, prev, pager, next"
                :total="486"
                :page-sizes="[10, 20, 50, 100]"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="举报奖励" name="reward">
        <el-row :gutter="12" style="margin: 16px 0 16px">
          <el-col :span="14">
            <div class="card card-orange">
              <div class="card-title">🏆 积分排行榜 · TOP 20（本月）</div>
              <el-table :data="rankRows" size="small" style="margin-top: 8px">
                <el-table-column label="排名" width="70" align="center">
                  <template #default="{ row }">
                    <span v-if="row.rank === 1" class="medal gold">🏆</span>
                    <span v-else-if="row.rank === 2" class="medal silver">🥈</span>
                    <span v-else-if="row.rank === 3" class="medal bronze">🥉</span>
                    <span v-else style="color: var(--color-text-secondary)">{{ row.rank }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="姓名" prop="name" width="100" />
                <el-table-column label="部门" prop="dept" width="120" />
                <el-table-column label="本月积分" width="110" align="center">
                  <template #default="{ row }">
                    <span style="font-weight: 600">{{ row.monthPoints }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="累计积分" width="110" align="center">
                  <template #default="{ row }">{{ row.totalPoints }}</template>
                </el-table-column>
                <el-table-column label="徽章" align="center">
                  <template #default="{ row }">
                    <el-tag v-for="b in row.badges" :key="b" size="small" effect="dark" style="margin-right: 4px; background: linear-gradient(135deg, #F59E0B, #D97706); border: none">{{ b }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
          <el-col :span="10">
            <div class="card card-green">
              <div class="card-title">积分规则说明</div>
              <ul class="rule-list">
                <li><el-tag type="success" size="small">+10</el-tag> 举报成功（任一渠道）</li>
                <li><el-tag type="danger" size="small">+50</el-tag> 举报经核实为真实钓鱼邮件</li>
                <li><el-tag type="warning" size="small">+100</el-tag> 月度积分排行榜 Top 10 额外奖励</li>
                <li><el-tag type="info" size="small">+20</el-tag> 连续 30 天无缺勤举报（每月至少1次）</li>
              </ul>
            </div>

            <div class="card card-blue" style="margin-top: 12px">
              <div class="card-title">我的积分卡片</div>
              <div class="my-points">
                <div class="points-row">
                  <div class="points-item">
                    <div class="points-label">当前总积分</div>
                    <div class="points-value total">2,380</div>
                  </div>
                  <div class="points-item">
                    <div class="points-label">本月积分</div>
                    <div class="points-value month">+320</div>
                  </div>
                </div>
                <div class="history-section">
                  <div class="section-title">历史奖励领取记录</div>
                  <div class="history-row"><span>2026-07-20</span><span>京东购物券 100元</span><span style="color: #10B981">-1000分</span></div>
                  <div class="history-row"><span>2026-06-18</span><span>学习卡 200元</span><span style="color: #10B981">-1800分</span></div>
                  <div class="history-row"><span>2026-05-30</span><span>月度荣誉证书（Top 8）</span><span style="color: #10B981">0分</span></div>
                </div>
              </div>
            </div>

            <div class="card card-red" style="margin-top: 12px">
              <div class="card-title">奖励兑换中心</div>
              <div class="reward-item">
                <div class="reward-icon">🛍️</div>
                <div class="reward-info">
                  <div class="reward-name">京东购物券 · 100元</div>
                  <div class="reward-cost">需要 <b>1,000</b> 积分（库存 28）</div>
                </div>
                <el-button size="small" type="danger" :disabled="2380 < 1000">兑换</el-button>
              </div>
              <el-divider style="margin: 8px 0" />
              <div class="reward-item">
                <div class="reward-icon">📚</div>
                <div class="reward-info">
                  <div class="reward-name">学习卡 · 极客时间 200元</div>
                  <div class="reward-cost">需要 <b>1,800</b> 积分（库存 12）</div>
                </div>
                <el-button size="small" type="danger" :disabled="2380 < 1800">兑换</el-button>
              </div>
              <el-divider style="margin: 8px 0" />
              <div class="reward-item">
                <div class="reward-icon">🏅</div>
                <div class="reward-info">
                  <div class="reward-name">季度安全卫士荣誉证书</div>
                  <div class="reward-cost">进入季度 Top 20 自动发放（免费）</div>
                </div>
                <el-button size="small" type="primary" disabled>需达标</el-button>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="realDialogVisible" title="真实钓鱼研判处置" width="520px">
      <div style="margin-bottom: 12px">
        <div style="font-size: 13px; color: var(--color-text-secondary); margin-bottom: 8px">
          邮件：<b style="color: var(--color-text-primary)">{{ currentReport?.subject }}</b>
        </div>
        <div style="font-size: 13px; color: var(--color-text-secondary)">
          发件人：<b style="color: var(--color-text-primary)">{{ currentReport?.sender }}</b>
        </div>
      </div>
      <el-form label-width="100px">
        <el-form-item label="处置选择">
          <el-checkbox-group v-model="disposalOptions">
            <el-checkbox value="push_soc">推送 SOC / SIEM</el-checkbox>
            <el-checkbox value="quarantine">隔离邮件（全邮箱搜索）</el-checkbox>
            <el-checkbox value="trace">启动溯源分析</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="处置备注">
          <el-input v-model="disposalRemark" type="textarea" :rows="3" placeholder="可选：记录研判依据、关联事件等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="realDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="realDialogVisible = false">确认提交处置</el-button>
      </template>
    </el-dialog>

    <!-- ============ 举报详情弹窗 ============ -->
    <el-dialog v-model="detailDialogVisible" title="举报详情" width="780px" destroy-on-close>
      <template v-if="currentReport">
        <!-- 举报人信息 -->
        <el-descriptions :column="4" size="small" border>
          <el-descriptions-item label="举报人">{{ currentReport.reporter }}</el-descriptions-item>
          <el-descriptions-item label="部门">{{ currentReport.reporterDept }}</el-descriptions-item>
          <el-descriptions-item label="举报时间">{{ currentReport.time }}</el-descriptions-item>
          <el-descriptions-item label="响应时间">3 分 12 秒</el-descriptions-item>
        </el-descriptions>

        <!-- 邮件预览 -->
        <div class="card" style="margin-top: 14px; border-top-color: var(--accent-red)">
          <div class="card-title">邮件预览</div>
          <div class="mail-meta">
            <div class="mail-meta-row"><span class="mail-meta-label">发件人</span><span class="mail-meta-value danger">{{ currentReport.sender }}</span></div>
            <div class="mail-meta-row"><span class="mail-meta-label">收件人</span><span class="mail-meta-value">{{ currentReport.reporter }} &lt;{{ currentReport.reporter }}@company.com&gt;</span></div>
            <div class="mail-meta-row"><span class="mail-meta-label">主题</span><span class="mail-meta-value"><b>{{ currentReport.subject }}</b></span></div>
          </div>
          <el-divider style="margin: 10px 0" />
          <div class="mail-body">
            尊敬的员工：<br /><br />
            系统检测到您的账户存在异常登录行为，为保障账户安全，请于 <b style="color: #f56c6c">24 小时内</b>
            点击下方链接完成身份验证，否则账户将被冻结。<br /><br />
            <a class="fake-link">立即验证账户安全 →</a><br /><br />
            此致<br />信息安全部
          </div>
        </div>

        <!-- 附件列表 -->
        <div class="card" style="margin-top: 12px">
          <div class="card-title">附件列表</div>
          <div v-for="att in detailAttachments" :key="att.name" class="attach-row">
            <el-icon><Document /></el-icon>
            <span style="flex: 1; font-size: 13px">{{ att.name }}</span>
            <span style="font-size: 12px; color: var(--color-text-tertiary)">{{ att.size }}</span>
            <el-tag :type="att.risk ? 'danger' : 'info'" size="small" effect="plain">{{ att.risk ? '高危' : '安全' }}</el-tag>
          </div>
          <el-empty v-if="!detailAttachments.length" description="无附件" :image-size="40" />
        </div>

        <!-- 邮件头详情 -->
        <div class="card" style="margin-top: 12px">
          <el-collapse v-model="headerCollapse">
            <el-collapse-item title="邮件头详情（溯源分析）" name="headers">
              <div v-for="h in detailHeaders" :key="h.key" class="header-row">
                <span class="header-key">{{ h.key }}</span>
                <span class="header-val">{{ h.value }}</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 处理操作 -->
        <div class="card card-teal" style="margin-top: 12px">
          <div class="card-title">处理操作</div>
          <el-radio-group v-model="detailAction" size="small">
            <el-radio-button value="drill">判定为演练邮件</el-radio-button>
            <el-radio-button value="real">判定为真实钓鱼</el-radio-button>
            <el-radio-button value="false">判定为误报</el-radio-button>
          </el-radio-group>
          <el-input v-model="detailRemark" type="textarea" :rows="2" placeholder="处理备注（可选）" style="margin-top: 10px" />
        </div>
      </template>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="submitDetailAction">提交处理结果</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Picture, Setting, Refresh, CopyDocument, RefreshRight, Document } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'

const activeTab = ref('plugin')
const reportDateRange = ref<[Date, Date] | null>(null)
const reportCategory = ref('')
const reportKw = ref('')
const realDialogVisible = ref(false)
const currentReport = ref<any>(null)
const disposalOptions = ref<string[]>([])
const disposalRemark = ref('')

const openRealDialog = (row: any) => {
  currentReport.value = row
  disposalOptions.value = []
  disposalRemark.value = ''
  realDialogVisible.value = true
}

// ============ 举报详情弹窗 ============
const detailDialogVisible = ref(false)
const headerCollapse = ref<string[]>(['headers'])
const detailAction = ref('drill')
const detailRemark = ref('')

const detailAttachments = [
  { name: '账户验证说明.pdf', size: '412 KB', risk: true },
  { name: '公司logo.png', size: '18 KB', risk: false },
]

const detailHeaders = [
  { key: 'Return-Path', value: '<bounce@phishing-shop.com>' },
  { key: 'Received', value: 'from mx.phishing-shop.com (203.0.113.66) by mail.company.com; Fri, 16 Aug 2026 11:40:21 +0800' },
  { key: 'DKIM', value: 'FAIL — 签名域 phishing-shop.com 与发件域不一致' },
  { key: 'SPF', value: 'SOFTFAIL — 203.0.113.66 不在授权发送列表中' },
  { key: 'DMARC', value: 'NONE — 发件域未配置 DMARC 策略' },
  { key: 'Message-ID', value: '<0a1b2c3d4e5f@phishing-shop.com>' },
  { key: 'Content-Type', value: 'multipart/mixed; boundary="----=_NextPart_000"' },
]

const openDetailDialog = (row: any) => {
  currentReport.value = row
  detailAction.value = row.manual || 'drill'
  detailRemark.value = ''
  detailDialogVisible.value = true
}

const submitDetailAction = () => {
  if (currentReport.value) currentReport.value.manual = detailAction.value
  detailDialogVisible.value = false
  ElMessage.success('处理结果已提交，分类已更新')
}

const apiConfig = reactive({
  endpoint: 'https://api.phishlab.example.com/v1/reports/mail',
  webhook: 'https://api.phishlab.example.com/v1/webhooks/mail-report',
  token: 'PL_sk_live_8f3a2c9d7e1b5f4a6b8c0d2e4f6a8b0c1d2e4f6a',
})

const regenerateToken = () => {
  apiConfig.token = 'PL_sk_live_' + Math.random().toString(36).slice(2, 42)
}

const reportRows = [
  { time: '2026-08-16 11:42:08', subject: '【紧急】8月工资条更新，请核对银行账户', sender: 'hr-notice@phishing-shop.com', reporter: '王建国', reporterDept: '行政部', auto: 'real', manual: '' },
  { time: '2026-08-16 10:28:31', subject: 'Q3全员防钓鱼演练 - 财务报销提醒', sender: 'no-reply@drill.phishlab.cn', reporter: '张小明', reporterDept: '财务部', auto: 'drill', manual: 'drill' },
  { time: '2026-08-16 09:15:02', subject: 'Re: 项目例会纪要（8月15日）', sender: 'project-team@example.com', reporter: '陈志强', reporterDept: '研发部', auto: 'false', manual: 'false' },
  { time: '2026-08-15 17:50:44', subject: 'Fedex 快递签收通知 - 运单号77889922', sender: 'fedex-express@service-alert.cc', reporter: '赵丽娟', reporterDept: '财务部', auto: 'real', manual: 'real' },
  { time: '2026-08-15 16:33:21', subject: '【VPN续费】账号即将冻结，请点击完成验证', sender: 'it-support@company-verification.top', reporter: '周文博', reporterDept: '技术部', auto: 'real', manual: 'real' },
  { time: '2026-08-15 14:19:07', subject: '报销审批通过 - 单据 #BZ20260814-0028', sender: 'workflow@example.com', reporter: '孙美玲', reporterDept: '人力资源部', auto: 'false', manual: 'false' },
  { time: '2026-08-15 11:05:55', subject: 'Q3演练-会议日程变更，请更新日历', sender: 'meeting@drill.phishlab.cn', reporter: '吴慧敏', reporterDept: '法务部', auto: 'drill', manual: 'drill' },
  { time: '2026-08-14 18:42:17', subject: '【重要】Google Drive 文件共享 - 员工手册 v3', sender: 'drive-shared@doc-share.xyz', reporter: '李晓华', reporterDept: '市场部', auto: 'real', manual: '' },
]

const rankRows = [
  { rank: 1, name: '王建国', dept: '行政部', monthPoints: 480, totalPoints: 3620, badges: ['月度冠军', '真实猎手'] },
  { rank: 2, name: '吴慧敏', dept: '法务部', monthPoints: 420, totalPoints: 2980, badges: ['举报达人'] },
  { rank: 3, name: '周文博', dept: '技术部', monthPoints: 380, totalPoints: 3150, badges: ['火眼金睛'] },
  { rank: 4, name: '陈志强', dept: '研发部', monthPoints: 340, totalPoints: 2560, badges: ['积极分子'] },
  { rank: 5, name: '孙美玲', dept: '人力资源部', monthPoints: 330, totalPoints: 2240, badges: [] },
  { rank: 6, name: '郑一帆', dept: '财务部', monthPoints: 310, totalPoints: 2480, badges: [] },
  { rank: 7, name: '钱海涛', dept: '市场部', monthPoints: 290, totalPoints: 1980, badges: [] },
  { rank: 8, name: '张小明', dept: '财务部', monthPoints: 320, totalPoints: 2380, badges: [] },
  { rank: 9, name: '赵丽娟', dept: '财务部', monthPoints: 260, totalPoints: 1820, badges: [] },
  { rank: 10, name: '李晓华', dept: '市场部', monthPoints: 250, totalPoints: 1760, badges: [] },
]
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.plugin-card {
  height: 100%;
}
.plugin-header {
  display: flex;
  align-items: center;
  gap: 14px;
}
.plugin-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  flex-shrink: 0;
}
.outlook-icon {
  background: linear-gradient(135deg, #378ADD22, #378ADD55);
}
.webmail-icon {
  background: linear-gradient(135deg, #10B98122, #10B98155);
}
.plugin-title-wrap {
  flex: 1;
}
.plugin-title {
  font-size: 15px;
  font-weight: 600;
}
.plugin-sub {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.plugin-section {
  margin-top: 16px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.step-list {
  padding-left: 20px;
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 2;
  code {
    background: var(--color-background-secondary);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
  }
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.code-section {
  margin-top: 20px;
}
.code-block {
  margin: 8px 0 0;
  background: #1e293b;
  color: #e2e8f0;
  padding: 14px 16px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.65;
  overflow-x: auto;
}
.medal {
  font-size: 18px;
}
.rule-list {
  list-style: none;
  padding: 0;
  margin: 0;
  li {
    padding: 8px 0;
    border-bottom: 1px dashed var(--color-border-tertiary);
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 10px;
    &:last-child { border-bottom: none; }
  }
}
.my-points {
  .points-row {
    display: flex;
    gap: 12px;
    margin: 4px 0 16px;
  }
  .points-item {
    flex: 1;
    text-align: center;
    padding: 12px;
    background: var(--color-background-secondary);
    border-radius: 10px;
  }
  .points-label {
    font-size: 12px;
    color: var(--color-text-secondary);
  }
  .points-value {
    font-size: 24px;
    font-weight: 600;
    margin-top: 4px;
    &.total { color: #378ADD; }
    &.month { color: #10B981; }
  }
}
.history-section {
  .section-title { margin-bottom: 6px; }
}
.history-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 6px 0;
  color: var(--color-text-secondary);
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border-bottom: none; }
}
.reward-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}
.reward-icon {
  width: 44px;
  height: 44px;
  background: var(--color-background-secondary);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.reward-info {
  flex: 1;
}
.reward-name {
  font-size: 13px;
  font-weight: 600;
}
.reward-cost {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}
.mail-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mail-meta-row {
  display: flex;
  gap: 10px;
  font-size: 12px;
}
.mail-meta-label {
  width: 52px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.mail-meta-value {
  color: var(--color-text-primary);
  word-break: break-all;
  &.danger { color: #f56c6c; font-weight: 600; }
}
.mail-body {
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-text-secondary);
  background: var(--color-background-secondary);
  border-radius: 8px;
  padding: 12px 14px;
}
.fake-link {
  color: #378add;
  text-decoration: underline;
  cursor: pointer;
}
.attach-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border-bottom: none; }
}
.header-row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 12px;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border-bottom: none; }
}
.header-key {
  width: 110px;
  flex-shrink: 0;
  font-weight: 600;
  color: var(--color-text-secondary);
  font-family: monospace;
}
.header-val {
  flex: 1;
  color: var(--color-text-primary);
  font-family: monospace;
  word-break: break-all;
}
</style>
