<template>
  <div class="page-container">
    <PageHeader title="智能助手">
      <template #actions>
        <el-button size="small" @click="tab = 'config'">查看使用统计</el-button>
        <el-button size="small" type="primary" @click="tab = 'config'">模型配置</el-button>
      </template>
    </PageHeader>

    <div class="card" style="margin: 16px 16px 16px">
      <el-tabs v-model="tab">
        <el-tab-pane label="AI对话助手" name="chat">
          <div class="chat-layout">
            <div class="chat-sidebar">
              <el-button type="primary" style="width: 100%; margin-bottom: 12px" :icon="Plus">新对话</el-button>
              <div class="history-item active" v-for="h in chatHistory" :key="h.id">
                <div class="history-title">{{ h.title }}</div>
                <div class="history-time">{{ h.time }}</div>
              </div>
            </div>
            <div class="chat-main">
              <div class="quick-tags">
                <el-tag v-for="q in quickQuestions" :key="q" type="info" effect="plain" class="quick-tag" @click="sendQuick(q)">
                  {{ q }}
                </el-tag>
              </div>
              <div class="messages">
                <div class="msg msg-user" v-for="(m, i) in messages" :key="i" :class="m.role">
                  <div class="msg-avatar" v-if="m.role === 'assistant'">AI</div>
                  <div class="msg-bubble">
                    <div v-html="m.content" />
                  </div>
                  <div class="msg-avatar user" v-if="m.role === 'user'">我</div>
                </div>
              </div>
              <div class="chat-input-area">
                <div class="input-wrap">
                  <el-input v-model="inputMsg" type="textarea" :rows="2" placeholder="请输入问题，Enter发送，Shift+Enter换行"
                    @keydown.enter.exact.prevent="sendMessage" resize="none" />
                  <div class="input-actions">
                    <el-button v-if="streaming" type="danger" size="small" @click="stopStream">停止</el-button>
                    <el-button type="primary" size="small" :disabled="!inputMsg" @click="sendMessage">
                      <el-icon><Promotion /></el-icon> 发送
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="AI模板生成" name="template">
          <el-row :gutter="12">
            <el-col :span="8">
              <div class="card card-blue">
                <div class="card-title">配置面板</div>
                <el-form label-width="90px" size="small">
                  <el-form-item label="场景">
                    <el-select v-model="tmplCfg.scene" style="width: 100%">
                      <el-option label="财务报销" value="finance" />
                      <el-option label="HR通知" value="hr" />
                      <el-option label="系统升级" value="system" />
                      <el-option label="中奖通知" value="prize" />
                      <el-option label="节假日问候" value="holiday" />
                      <el-option label="其他" value="other" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="目标人群">
                    <el-select v-model="tmplCfg.audience" style="width: 100%">
                      <el-option label="全员" value="all" />
                      <el-option label="财务部" value="finance" />
                      <el-option label="新员工" value="new" />
                      <el-option label="高管" value="exec" />
                      <el-option label="研发部" value="rd" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="语气风格">
                    <el-select v-model="tmplCfg.tone" style="width: 100%">
                      <el-option label="正式严肃" value="formal" />
                      <el-option label="亲切友好" value="friendly" />
                      <el-option label="紧急警告" value="urgent" />
                      <el-option label="幽默风趣" value="humor" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="语言">
                    <el-radio-group v-model="tmplCfg.lang">
                      <el-radio value="zh">中文</el-radio>
                      <el-radio value="en">英文</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item label="难度等级">
                    <el-radio-group v-model="tmplCfg.difficulty">
                      <el-radio value="low">低</el-radio>
                      <el-radio value="mid">中</el-radio>
                      <el-radio value="high">高</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item label="温度系数">
                    <el-slider v-model="tmplCfg.temperature" :min="0" :max="2" :step="0.1" show-input />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" :icon="MagicStick" @click="generateTmpl">生成</el-button>
                    <el-button :icon="Refresh" :disabled="!generatedTmpl" @click="generateTmpl">重新生成</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
            <el-col :span="16">
              <div class="card card-green" v-if="generatedTmpl">
                <div class="card-title">
                  实时预览
                  <el-button size="small" link @click="previewVisible = true">大图预览</el-button>
                </div>
                <el-row :gutter="12">
                  <el-col :span="12">
                    <div class="preview-field">
                      <span class="preview-label">主题：</span>
                      <span class="preview-value">{{ generatedTmpl.subject }}</span>
                    </div>
                    <div class="preview-field">
                      <span class="preview-label">建议发件人：</span>
                      <span class="preview-value">{{ generatedTmpl.sender_name }} &lt;{{ generatedTmpl.sender_email }}&gt;</span>
                    </div>
                    <div class="preview-field">
                      <span class="preview-label">落地页类型：</span>
                      <el-tag size="small" type="info">{{ generatedTmpl.landing_type }}</el-tag>
                    </div>
                    <div class="preview-field">
                      <span class="preview-label">预估点击率：</span>
                      <span class="preview-value highlight">{{ generatedTmpl.estimated_ctr }}%</span>
                    </div>
                  </el-col>
                  <el-col :span="12">
                    <div class="preview-actions">
                      <el-button size="small" type="primary">直接使用</el-button>
                      <el-button size="small">编辑后入库</el-button>
                      <el-button size="small">重新生成</el-button>
                      <el-button size="small" :icon="Star" plain>收藏</el-button>
                    </div>
                  </el-col>
                </el-row>
                <div class="email-preview">
                  <div class="email-body" v-html="generatedTmpl.body" />
                </div>
              </div>
              <el-alert v-else type="info" :closable="false" show-icon title="请在左侧配置参数后点击「生成」按钮预览内容" />

              <div class="card card-purple" style="margin-top: 12px">
                <div class="card-title">生成历史</div>
                <AiDraftCard v-for="d in drafts" :key="d.id" :draft="d"
                  @preview="previewDraft" @approve="approveDraft" @discard="discardDraft" />
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="智能分析报告" name="report">
          <el-row :gutter="12">
            <el-col :span="6">
              <div class="card card-teal report-nav-card" :class="{ active: reportType === 'effect' }" @click="reportType = 'effect'">
                <div class="rn-icon">📊</div>
                <div class="rn-title">演练效果分析</div>
                <div class="rn-desc">投入产出比、转化率、中招率拆解</div>
              </div>
              <div class="card card-red report-nav-card" :class="{ active: reportType === 'dept' }" @click="reportType = 'dept'" style="margin-top: 12px">
                <div class="rn-icon">🏢</div>
                <div class="rn-title">部门风险画像</div>
                <div class="rn-desc">跨部门横向对比风险等级</div>
              </div>
              <div class="card card-orange report-nav-card" :class="{ active: reportType === 'trend' }" @click="reportType = 'trend'" style="margin-top: 12px">
                <div class="rn-icon">📈</div>
                <div class="rn-title">趋势预测</div>
                <div class="rn-desc">基于历史数据的风险趋势预测</div>
              </div>
              <div class="card card-blue report-nav-card" :class="{ active: reportType === 'training' }" @click="reportType = 'training'" style="margin-top: 12px">
                <div class="rn-icon">🎓</div>
                <div class="rn-title">培训建议</div>
                <div class="rn-desc">基于薄弱点的个性化培训推荐</div>
              </div>
            </el-col>
            <el-col :span="18">
              <div class="card card-blue">
                <div class="card-title">
                  <span>分析面板 · {{ reportLabel }}</span>
                  <div>
                    <el-select size="small" v-model="reportTarget" style="width: 220px">
                      <el-option label="Q3全员防钓鱼演练" value="q3" />
                      <el-option label="Q2全员防钓鱼演练" value="q2" />
                      <el-option label="财务人员专项演练" value="finance" />
                    </el-select>
                    <el-button size="small" type="primary" style="margin-left: 8px">生成报告</el-button>
                    <el-button size="small" style="margin-left: 4px">导出PDF</el-button>
                    <el-button size="small" style="margin-left: 4px">分享</el-button>
                  </div>
                </div>

                <div class="card card-blue nested-card">
                  <div class="card-title">执行摘要</div>
                  <p>本次Q3全员防钓鱼演练覆盖 <strong>3,580 人</strong>，整体中招率 <strong>15.6%</strong>，较上季度下降 4.2 个百分点，说明安全培训初见成效。</p>
                  <p>财务部中招率 <strong>32%</strong> 仍然显著偏高，建议开展专项培训；研发部表现最优（中招率 9%），可作为内部安全文化标杆推广。</p>
                  <p>短信渠道点击率较邮件高 8%，但样本量较小，建议下季度扩大短信演练范围以验证数据显著性。</p>
                </div>

                <el-row :gutter="12" style="margin-top: 12px">
                  <el-col :span="4" v-for="k in keyFindings" :key="k.label">
                    <StatCard :title="k.label" :value="k.value" :suffix="k.suffix" :accent="k.accent" />
                  </el-col>
                </el-row>

                <div class="card card-orange nested-card" style="margin-top: 12px">
                  <div class="card-title">关键发现</div>
                  <ul class="bullet-list">
                    <li>邮件正文含「附件」「更新」「紧急」关键词时点击率提升 40%</li>
                    <li>工作日 9:00-10:00 为打开高峰，中招概率比其他时段高 2.3 倍</li>
                    <li>Chrome + Windows 用户群体中招率显著高于其他组合</li>
                    <li>首次点击平均响应时间 8 秒，熟练用户 < 5 秒更容易中招</li>
                  </ul>
                </div>

                <div class="card card-green nested-card" style="margin-top: 12px">
                  <div class="card-title">改进建议</div>
                  <div v-for="s in suggestions" :key="s.text" class="suggestion-row">
                    <el-tag size="small" :type="s.priority === '高' ? 'danger' : s.priority === '中' ? 'warning' : 'info'">{{ s.priority }}优先</el-tag>
                    <span class="suggestion-text">{{ s.text }}</span>
                  </div>
                </div>

                <div class="card card-red nested-card" style="margin-top: 12px">
                  <div class="card-title">风险预警</div>
                  <div v-for="w in riskWarnings" :key="w.text" class="warning-row">
                    <el-tag size="small" :type="w.level === '高危' ? 'danger' : 'warning'" effect="dark">{{ w.level }}</el-tag>
                    <span class="warning-text">{{ w.text }}</span>
                  </div>
                </div>

                <el-row :gutter="12" style="margin-top: 12px">
                  <el-col :span="12">
                    <div class="card card-red nested-card">
                      <div class="card-title">转化漏斗</div>
                      <BaseChart :option="funnelChart" height="260px" />
                    </div>
                  </el-col>
                  <el-col :span="12">
                    <div class="card card-purple nested-card">
                      <div class="card-title">部门对比</div>
                      <BaseChart :option="deptChart" height="260px" />
                    </div>
                  </el-col>
                </el-row>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="AI配置" name="config">
          <el-row :gutter="12">
            <el-col :span="12">
              <div class="card card-blue">
                <div class="card-title">模型选择</div>
                <el-radio-group v-model="cfg.model" style="display: flex; flex-direction: column; gap: 8px">
                  <el-radio value="gpt4o">GPT-4o <el-tag size="small" type="success">推荐</el-tag></el-radio>
                  <el-radio value="claude35">Claude 3.5 Sonnet</el-radio>
                  <el-radio value="ernie">文心一言</el-radio>
                  <el-radio value="qwen">通义千问</el-radio>
                  <el-radio value="local">本地模型 (Ollama / vLLM)</el-radio>
                </el-radio-group>
                <el-divider />
                <el-form label-width="100px" size="small">
                  <el-form-item label="API端点">
                    <el-input v-model="cfg.endpoint" placeholder="https://api.openai.com/v1" />
                  </el-form-item>
                  <el-form-item label="API Key">
                    <el-input v-model="cfg.apiKey" :type="showKey ? 'text' : 'password'" placeholder="sk-...">
                      <template #append>
                        <el-button @click="showKey = !showKey">{{ showKey ? '隐藏' : '显示' }}</el-button>
                      </template>
                    </el-input>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-green">
                <div class="card-title">参数调节</div>
                <el-form label-width="110px" size="small">
                  <el-form-item label="温度 Temperature">
                    <el-slider v-model="cfg.temperature" :min="0" :max="2" :step="0.1" show-input />
                  </el-form-item>
                  <el-form-item label="最大 Token">
                    <el-input-number v-model="cfg.maxTokens" :min="128" :max="32768" :step="128" style="width: 100%" />
                  </el-form-item>
                  <el-form-item label="Top-P">
                    <el-slider v-model="cfg.topP" :min="0" :max="1" :step="0.05" show-input />
                  </el-form-item>
                  <el-form-item label="系统提示词">
                    <el-input v-model="cfg.systemPrompt" type="textarea" :rows="4" placeholder="You are a helpful security assistant..." />
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
          </el-row>

          <el-row :gutter="12" style="margin-top: 12px">
            <el-col :span="12">
              <div class="card card-orange">
                <div class="card-title">数据安全</div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">脱敏处理</div>
                    <div class="toggle-desc">发送前自动脱敏姓名、邮箱、手机等PII字段</div>
                  </div>
                  <el-switch v-model="cfg.maskPII" />
                </div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">数据不外发模式</div>
                    <div class="toggle-desc">仅使用本地模型，禁止任何外部API调用</div>
                  </div>
                  <el-switch v-model="cfg.localOnly" />
                </div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">对话记录保存</div>
                    <div class="toggle-desc">保存对话历史便于审计追溯</div>
                  </div>
                  <el-switch v-model="cfg.saveHistory" />
                </div>
                <el-form label-width="110px" size="small" style="margin-top: 12px">
                  <el-form-item label="保存期限">
                    <el-select v-model="cfg.historyDays" style="width: 200px">
                      <el-option :value="7" label="7 天" />
                      <el-option :value="30" label="30 天" />
                      <el-option :value="90" label="90 天" />
                      <el-option :value="365" label="365 天" />
                    </el-select>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-purple">
                <div class="card-title">功能开关</div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">AI对话</div>
                    <div class="toggle-desc">全局启用自然语言对话助手</div>
                  </div>
                  <el-switch v-model="cfg.featChat" />
                </div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">AI模板生成</div>
                    <div class="toggle-desc">自动生成钓鱼演练邮件/短信模板</div>
                  </div>
                  <el-switch v-model="cfg.featTmpl" />
                </div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">智能分析</div>
                    <div class="toggle-desc">AI自动生成演练分析报告和洞察</div>
                  </div>
                  <el-switch v-model="cfg.featReport" />
                </div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">自动培训推荐</div>
                    <div class="toggle-desc">基于薄弱点推荐个性化培训课程</div>
                  </div>
                  <el-switch v-model="cfg.featTrain" />
                </div>
              </div>
            </el-col>
          </el-row>

          <div class="card card-teal" style="margin-top: 12px">
            <div class="card-title">
              使用统计
              <el-button type="primary" size="small">保存配置</el-button>
            </div>
            <el-row :gutter="12">
              <el-col :span="6" v-for="s in usageStats" :key="s.title">
                <StatCard :title="s.title" :value="s.value" :suffix="s.suffix" :accent="s.accent" />
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="previewVisible" title="模板预览" width="680px">
      <div v-if="generatedTmpl" class="dialog-preview">
        <div class="dp-row"><span class="dp-label">主题：</span>{{ generatedTmpl.subject }}</div>
        <div class="dp-row"><span class="dp-label">发件人：</span>{{ generatedTmpl.sender_name }} &lt;{{ generatedTmpl.sender_email }}&gt;</div>
        <div class="dp-row"><span class="dp-label">落地页：</span>{{ generatedTmpl.landing_type }}</div>
        <div class="dp-row"><span class="dp-label">预估CTR：</span>{{ generatedTmpl.estimated_ctr }}%</div>
        <el-divider />
        <div class="email-body-large" v-html="generatedTmpl.body" />
        <el-divider />
        <div style="display: flex; gap: 8px; justify-content: flex-end">
          <el-button>收藏</el-button>
          <el-button>编辑后入库</el-button>
          <el-button type="primary">直接使用</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import { Plus, MagicStick, Refresh, Star, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/api'
import { postSSE } from '@/composables/useSSE'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import BaseChart from '@/components/base/BaseChart.vue'
import AiDraftCard, { type AiDraft } from '@/components/ai/AiDraftCard.vue'

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'

const tab = ref<'chat' | 'template' | 'report' | 'config'>('chat')

const chatHistory = ref([
  { id: 1, title: '分析Q3演练效果', time: '2小时前' },
  { id: 2, title: '生成财务钓鱼模板', time: '昨天' },
  { id: 3, title: '风险评估建议', time: '昨天' },
  { id: 4, title: '培训课程推荐', time: '3天前' },
  { id: 5, title: '查询员工风险画像', time: '上周' },
])

const quickQuestions = [
  '分析演练效果', '生成钓鱼模板', '风险评估建议', '培训推荐', '查询员工画像',
]

const messages = ref<{ role: 'user' | 'assistant'; content: string }[]>([
  { role: 'assistant', content: '您好！我是PhishLab智能助手，擅长钓鱼演练数据分析、模板生成和安全建议。有什么可以帮您的？' },
  { role: 'user', content: '帮我分析一下Q3全员演练的效果如何？' },
  { role: 'assistant', content: '根据数据，**Q3全员防钓鱼演练**整体表现：\n\n- 📊 参与人数：<strong>3,580 人</strong>\n- 📧 投递率：<strong>100%</strong> | 打开率：<strong>71.3%</strong>\n- 🔗 点击率：<strong>27.0%</strong> | 中招率：<strong>15.6%</strong>\n- 🛡️ 举报率：<strong>22.3%</strong>\n\n**与上季度对比**：中招率下降 <span style="color:#1d9e75">4.2%</span> 个百分点，培训效果显著。但 <span style="color:#a32d2d">财务部(32%)</span> 仍为高风险部门，建议开展 <strong>专项培训</strong>。需要生成完整分析报告吗？' },
])
const inputMsg = ref('')
const streaming = ref(false)
const sessionId = ref<number | null>(null)
let abort: (() => void) | null = null

function sendQuick(q: string) {
  inputMsg.value = q
  sendMessage()
}

function sendMessage() {
  const text = inputMsg.value.trim()
  if (!text || streaming.value) return
  messages.value.push({ role: 'user', content: text })
  inputMsg.value = ''
  const answer = { role: 'assistant' as const, content: '' }
  messages.value.push(answer)
  streaming.value = true

  abort = postSSE({
    url: '/api/v1/ai/chat/stream',
    body: { session_id: sessionId.value, message: text, page_context: {} },
    onFrame: (frame) => {
      if (frame.type === 'token' && frame.content) {
        answer.content += frame.content
      } else if (frame.type === 'error') {
        answer.content += `\n\n> ${frame.message || '生成失败，请重试'}`
      }
    },
    onError: (err) => {
      answer.content = `生成失败：${err.message}`
      streaming.value = false
    },
    onClose: () => {
      streaming.value = false
    },
  })
}

function stopStream() {
  abort?.()
  streaming.value = false
  ElMessage.info('已停止生成')
}

const tmplCfg = reactive({
  scene: 'finance', audience: 'all', tone: 'formal', lang: 'zh',
  difficulty: 'mid', temperature: 0.7,
})

const generatedTmpl = ref<null | {
  subject: string; sender_name: string; sender_email: string;
  landing_type: string; estimated_ctr: number; body: string;
}>(null)
const previewVisible = ref(false)

function generateTmpl() {
  generatedTmpl.value = {
    subject: '【紧急】Q3差旅费报销截止通知（请于本周五前完成）',
    sender_name: '财务部 · 张会计', sender_email: 'zhang.acc@corp-payroll-service.cn',
    landing_type: '企业邮箱登录页', estimated_ctr: 38,
    body: `
      <p style="font-family:Arial,sans-serif;color:#333;line-height:1.6">
      <strong>各位同事：</strong></p>
      <p>2026年Q3差旅费报销窗口将于 <strong style="color:#a32d2d">8月22日（本周五）18:00</strong> 截止，逾期将推迟至下季度结算。</p>
      <p>请尽快登录报销系统提交：</p>
      <p style="text-align:center"><a href="#" style="display:inline-block;padding:10px 28px;background:#378add;color:#fff;text-decoration:none;border-radius:6px">
      📎 立即进入报销系统</a></p>
      <p style="color:#888;font-size:12px;margin-top:20px">—— 财务共享服务中心 · 内部通知</p>`,
  }
  ElMessage.success('模板生成成功')
  // 本地预览保持现状，同时后台生成草稿并刷新待审核列表
  aiApi.generateTemplate({ ...tmplCfg }).then(() => loadDrafts()).catch(() => {})
}

const mockDrafts: AiDraft[] = [
  { id: 1, biz_type: 'email_template', title: '【紧急】Q3差旅费报销截止通知', content: '各位同事：2026年Q3差旅费报销窗口将于8月22日截止...', status: 'draft' },
  { id: 2, biz_type: 'email_template', title: '企业邮箱存储已满 - 请立即验证账户', content: '尊敬的用户：您的企业邮箱存储空间已使用95%...', status: 'approved', reviewer: '王安全', reviewed_at: '2026-08-14 15:30' },
  { id: 3, biz_type: 'sms_template', title: '【HR通知】8月工资条已发送，请查收', content: '尊敬的员工，您8月工资条已生成...', status: 'draft' },
]
const drafts = ref<AiDraft[]>(mockDrafts)

async function loadDrafts() {
  try {
    const data = (await aiApi.drafts()) as AiDraft[]
    if (Array.isArray(data)) drafts.value = data
  } catch {
    ElMessage.warning('接口数据加载失败，已展示演示数据')
  }
}

function previewDraft(d: AiDraft) { previewVisible.value = true }
function approveDraft(d: AiDraft) {
  aiApi.approveDraft(d.id)
    .then(() => {
      ElMessage.success(`草稿「${d.title}」已确认入库`)
      loadDrafts()
    })
    .catch(() => {})
}
function discardDraft(d: AiDraft) {
  aiApi.discardDraft(d.id)
    .then(() => {
      ElMessage.warning(`草稿「${d.title}」已丢弃`)
      loadDrafts()
    })
    .catch(() => {})
}

const reportType = ref<'effect' | 'dept' | 'trend' | 'training'>('effect')
const reportTarget = ref('q3')

const reportLabel = computed(() => ({
  effect: '演练效果分析', dept: '部门风险画像',
  trend: '趋势预测', training: '培训建议',
}[reportType.value]))

const keyFindings = [
  { label: '总体中招率', value: '15.6', suffix: '%', accent: 'red' as Accent },
  { label: '较上季度', value: '↓4.2', suffix: '%', accent: 'green' as Accent },
  { label: '最高风险部门', value: '财务部', suffix: ' 32%', accent: 'orange' as Accent },
  { label: '举报率提升', value: '+8.7', suffix: '%', accent: 'teal' as Accent },
]

const suggestions = [
  { priority: '高', text: '财务部立即开展专项培训 + 1v1 重点辅导（56人）' },
  { priority: '高', text: '下季度新增短信/微信渠道演练，覆盖移动端薄弱点' },
  { priority: '中', text: '针对9-10点高峰时段，优化钓鱼诱饵时间分布' },
  { priority: '中', text: '建立「安全之星」内部宣传机制，推广研发部经验' },
  { priority: '低', text: '完善钓鱼邮件举报快速通道入口，提升举报率' },
]

const riskWarnings = [
  { level: '高危', text: '12 名员工连续 2 次演练中招且未参加任何培训，建议立即纳入强制培训名单' },
  { level: '高危', text: '财务部 3 名员工在演练中提交了真实密码格式的输入，存在真实泄露风险' },
  { level: '中危', text: '市场部举报率仅 6%，远低于全司平均 22.3%，安全反馈渠道触达不足' },
]

const funnelChart: EChartsOption = {
  tooltip: { trigger: 'item', formatter: '{b}: {c}' },
  series: [{
    type: 'funnel', left: '10%', width: '80%', minSize: '20%',
    label: { show: true, position: 'inside', fontSize: 11 },
    data: [
      { value: 3580, name: '投递成功' },
      { value: 2550, name: '已阅读' },
      { value: 966, name: '已点击' },
      { value: 558, name: '输入信息' },
      { value: 187, name: '中招提交' },
    ],
  }],
}

const deptChart: EChartsOption = {
  tooltip: { trigger: 'axis' },
  grid: { left: 80, right: 20, top: 10, bottom: 20 },
  xAxis: { type: 'value', max: 40, axisLabel: { formatter: '{value}%' } },
  yAxis: { type: 'category', data: ['研发部', '法务部', '人力资源部', '行政部', '市场部', '财务部'] },
  series: [{
    type: 'bar', barWidth: 16,
    data: [9, 12, 17, 21, 26, 32],
    itemStyle: { color: (p: any) => ['#1d9e75', '#378add', '#7f77dd', '#0d9488', '#d85a30', '#a32d2d'][p.dataIndex] },
    label: { show: true, position: 'right', formatter: '{c}%' },
  }],
}

const showKey = ref(false)
const cfg = reactive({
  model: 'gpt4o',
  endpoint: 'https://api.openai.com/v1',
  apiKey: 'sk-************************************************',
  temperature: 0.7, maxTokens: 4096, topP: 0.95,
  systemPrompt: 'You are a professional cybersecurity assistant specialized in phishing simulation and security awareness training for enterprises.',
  maskPII: true, localOnly: false, saveHistory: true, historyDays: 90,
  featChat: true, featTmpl: true, featReport: true, featTrain: true,
})

const usageStats: { title: string; value: string | number; suffix: string; accent: Accent }[] = [
  { title: '总调用次数', value: '12,486', suffix: ' 次', accent: 'blue' },
  { title: '本月调用', value: '3,258', suffix: ' 次', accent: 'green' },
  { title: 'Token消耗', value: '8.4M', suffix: '', accent: 'orange' },
  { title: '费用预估', value: '¥2,186', suffix: '', accent: 'purple' },
]

onMounted(() => {
  // 历史会话
  aiApi.sessions()
    .then((data) => {
      const list = data as { id: number; title: string; time: string }[]
      if (Array.isArray(list) && list.length) chatHistory.value = list
    })
    .catch(() => ElMessage.warning('接口数据加载失败，已展示演示数据'))
  // AI 生成草稿（待审核列表）
  loadDrafts()
})
</script>

<style scoped lang="scss">
.chat-layout {
  display: flex;
  min-height: 520px;
  gap: 12px;
}
.chat-sidebar {
  width: 25%;
  background: var(--color-background-secondary);
  border-radius: 8px;
  padding: 12px;
  min-width: 0;
}
.history-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  &.active, &:hover { background: rgba(55,138,221,0.1); }
}
.history-title { font-size: 13px; font-weight: 500; }
.history-time { font-size: 11px; color: var(--color-text-tertiary); margin-top: 2px; }

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-background-secondary);
  border-radius: 8px;
  padding: 12px;
  gap: 12px;
}
.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.quick-tag { cursor: pointer; }

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  &.msg-user { justify-content: flex-end; }
}
.msg-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--accent-blue); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600;
  flex-shrink: 0;
  &.user { background: var(--accent-teal); }
}
.msg-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff;
  line-height: 1.6;
  font-size: 13px;
  :deep(p) { margin: 4px 0; }
}
.msg-user .msg-bubble {
  background: var(--accent-blue); color: #fff;
  a, strong { color: #fff; }
}

.chat-input-area { }
.input-wrap {
  background: #fff;
  border-radius: 8px;
  padding: 8px;
  border: 1px solid var(--color-border-tertiary);
}
.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 6px;
}

.preview-field { margin-bottom: 10px; font-size: 13px; }
.preview-label { color: var(--color-text-secondary); }
.preview-value.highlight { color: var(--accent-red); font-weight: 600; font-size: 15px; }
.preview-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.email-preview {
  margin-top: 14px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  padding: 20px;
  background: #fafafa;
}
.email-body :deep(a) { color: var(--accent-blue); }

.report-nav-card {
  cursor: pointer;
  &.active { border-color: var(--color-border-info); background: var(--color-background-info); }
}
.rn-icon { font-size: 28px; }
.rn-title { font-size: 14px; font-weight: 600; margin-top: 6px; }
.rn-desc { font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px; }

.nested-card { margin: 0; }
.bullet-list { margin: 0; padding-left: 18px; font-size: 13px; line-height: 2; }
.suggestion-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border: 0; }
}
.suggestion-text { font-size: 13px; }
.warning-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border: 0; }
}
.warning-text { font-size: 13px; line-height: 1.5; }

.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border: 0; }
}
.toggle-title { font-size: 13px; font-weight: 500; }
.toggle-desc { font-size: 11px; color: var(--color-text-tertiary); margin-top: 2px; }

.dialog-preview { font-size: 13px; }
.dp-row { padding: 4px 0; }
.dp-label { color: var(--color-text-secondary); display: inline-block; width: 80px; }
.email-body-large {
  background: #fafafa;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  padding: 24px;
  line-height: 1.8;
}
</style>
