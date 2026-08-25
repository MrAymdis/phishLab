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
                <div class="card-title">
                  LLM Provider
                  <el-button type="primary" size="small" @click="openCreate">新增 Provider</el-button>
                </div>
                <div v-if="providers.length" class="prov-list">
                  <div v-for="p in providers" :key="p.id" class="prov-row" :class="{ active: p.id === selectedId }"
                       @click="selectProvider(p)">
                    <div class="prov-head">
                      <span class="prov-name">{{ p.name }}</span>
                      <el-tag size="small" :type="p.enabled ? 'success' : 'info'">{{ typeLabel(p.type) }}</el-tag>
                      <span class="prov-model">{{ p.model || '—' }}</span>
                    </div>
                    <div class="prov-meta">
                      <span class="prov-key">{{ p.api_key_masked || '未配置 Key' }}</span>
                      <span class="prov-usage">{{ p.usage_7d.calls }} 次 / 7天</span>
                    </div>
                    <div class="prov-ops" @click.stop>
                      <el-button link size="small" :loading="testingId === p.id" @click="testProvider(p)">测试</el-button>
                      <el-button link size="small" @click="openEdit(p)">编辑</el-button>
                      <el-button link size="small" type="danger" @click="removeProvider(p)">删除</el-button>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无 Provider，请先新增" :image-size="64" />
                <div class="prov-hint">AI 对话 / 模板生成 / 智能分析 / ChatBI 共用同一 Provider；无可用 Provider 时自动降级本地实现。</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-green">
                <div class="card-title">
                  参数调节
                  <el-button type="primary" size="small" :disabled="!selectedProvider" @click="saveParams">保存参数</el-button>
                </div>
                <template v-if="selectedProvider">
                  <el-form label-width="110px" size="small">
                    <el-form-item label="温度 Temperature">
                      <el-slider v-model="paramForm.temperature" :min="0" :max="2" :step="0.1" show-input />
                    </el-form-item>
                    <el-form-item label="最大 Token">
                      <el-input-number v-model="paramForm.maxTokens" :min="1" :max="16384" :step="128" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="系统提示词">
                      <el-input v-model="paramForm.systemPrompt" type="textarea" :rows="5"
                                placeholder="You are a helpful security assistant..." />
                    </el-form-item>
                  </el-form>
                </template>
                <el-empty v-else description="请先选择左侧 Provider" :image-size="64" />
              </div>
            </el-col>
          </el-row>

          <el-row :gutter="12" style="margin-top: 12px">
            <el-col :span="12">
              <div class="card card-orange">
                <div class="card-title">数据安全</div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">启用 Provider</div>
                    <div class="toggle-desc">停用后 AI 功能自动降级本地实现</div>
                  </div>
                  <el-switch :model-value="!!selectedProvider?.enabled" :disabled="!selectedProvider"
                             @change="toggleEnabled" />
                </div>
                <div class="toggle-row">
                  <div>
                    <div class="toggle-title">数据不外发模式</div>
                    <div class="toggle-desc">仅允许本地模型，云端 Provider 将被禁止调用（红线：敏感数据不外发）</div>
                  </div>
                  <el-switch :model-value="localOnly" :disabled="!selectedProvider" @change="toggleLocalOnly" />
                </div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-purple">
                <div class="card-title">使用统计（近 7 天）</div>
                <el-row :gutter="12">
                  <el-col :span="6" v-for="s in usageStats" :key="s.title">
                    <StatCard :title="s.title" :value="s.value" :suffix="s.suffix" :accent="s.accent" />
                  </el-col>
                </el-row>
              </div>
            </el-col>
          </el-row>

          <!-- 新增 / 编辑 Provider 对话框 -->
          <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 Provider' : '新增 Provider'" width="520px">
            <el-form label-width="110px" size="small">
              <el-form-item label="名称" required>
                <el-input v-model="providerForm.name" placeholder="如：OpenAI 主账号" maxlength="64" />
              </el-form-item>
              <el-form-item label="类型" required>
                <el-select v-model="providerForm.type" style="width: 100%">
                  <el-option v-for="t in PROVIDER_TYPES" :key="t.value" :value="t.value" :label="t.label"
                             :disabled="t.value === 'wenxin'" />
                </el-select>
              </el-form-item>
              <el-form-item label="API端点">
                <el-input v-model="providerForm.endpoint" placeholder="https://api.openai.com/v1" />
              </el-form-item>
              <el-form-item :label="providerForm.type === 'local' ? 'API Key（可空）' : 'API Key'">
                <el-input v-model="providerForm.apiKey" :type="showKey ? 'text' : 'password'"
                          :placeholder="editingId ? '留空表示不更换' : 'sk-...'">
                  <template #append>
                    <el-button @click="showKey = !showKey">{{ showKey ? '隐藏' : '显示' }}</el-button>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="模型">
                <el-input v-model="providerForm.model" placeholder="如 gpt-4o-mini / deepseek-chat" />
              </el-form-item>
              <el-form-item label="启用">
                <el-switch v-model="providerForm.enabled" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button size="small" @click="dialogVisible = false">取消</el-button>
              <el-button type="primary" size="small" :loading="saving" @click="submitProvider">保存</el-button>
            </template>
          </el-dialog>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi, type AiProviderItem } from '@/api'
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

const PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI 兼容（OpenAI / DeepSeek / One-API）' },
  { value: 'claude', label: 'Claude (Anthropic)' },
  { value: 'tongyi', label: '通义千问' },
  { value: 'local', label: '本地模型 (Ollama / vLLM)' },
  { value: 'wenxin', label: '文心一言（暂未接入）' },
]
const TYPE_LABELS: Record<string, string> = {
  openai: 'OpenAI', claude: 'Claude', tongyi: '通义千问',
  wenxin: '文心一言', local: '本地',
}

const providers = ref<AiProviderItem[]>([])
const selectedId = ref<number | null>(null)
const selectedProvider = computed(() => providers.value.find(p => p.id === selectedId.value) ?? null)
const testingId = ref<number | null>(null)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const providerForm = reactive({
  name: '', type: 'openai', endpoint: '', apiKey: '', model: '', enabled: true,
})
const paramForm = reactive({ temperature: 0.7, maxTokens: 2048, systemPrompt: '' })

/** 数据不外发 = data_outbound 取反（后端：false 时仅本地模型可调用） */
const localOnly = computed(() => selectedProvider.value ? !selectedProvider.value.data_outbound : false)

const usageStats = computed(() => {
  const s = providers.value.reduce((acc, p) => {
    acc.calls += p.usage_7d?.calls || 0
    acc.tokens_in += p.usage_7d?.tokens_in || 0
    acc.tokens_out += p.usage_7d?.tokens_out || 0
    acc.enabled += p.enabled ? 1 : 0
    return acc
  }, { calls: 0, tokens_in: 0, tokens_out: 0, enabled: 0 })
  const fmt = (n: number) => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n.toLocaleString()
  return [
    { title: '调用次数', value: s.calls.toLocaleString(), suffix: ' 次', accent: 'blue' as Accent },
    { title: 'Token 消耗', value: fmt(s.tokens_in + s.tokens_out), suffix: '', accent: 'orange' as Accent },
    { title: '输入 Token', value: fmt(s.tokens_in), suffix: '', accent: 'green' as Accent },
    { title: '启用 Provider', value: `${s.enabled}/${providers.value.length}`, suffix: '', accent: 'purple' as Accent },
  ]
})

function typeLabel(t: string) { return TYPE_LABELS[t] || t }

async function loadProviders() {
  try {
    const data = await aiApi.providers()
    providers.value = data
    if (!selectedId.value || !data.some(p => p.id === selectedId.value)) {
      selectedId.value = data[0]?.id ?? null
    }
    applyParams()
  } catch {
    ElMessage.warning('Provider 列表加载失败，请检查 ai:manage 权限')
  }
}

function selectProvider(p: AiProviderItem) {
  selectedId.value = p.id
  applyParams()
}

function applyParams() {
  const p = selectedProvider.value
  if (p) {
    paramForm.temperature = p.temperature
    paramForm.maxTokens = p.max_tokens
    paramForm.systemPrompt = p.system_prompt ?? ''
  }
}

function saveParams() {
  const p = selectedProvider.value
  if (!p) return
  aiApi.updateProvider(p.id, {
    temperature: paramForm.temperature,
    max_tokens: paramForm.maxTokens,
    system_prompt: paramForm.systemPrompt,
  })
    .then(() => { ElMessage.success(`「${p.name}」参数已保存`); loadProviders() })
    .catch((e) => ElMessage.error(e?.message || '保存失败'))
}

function toggleEnabled(v: boolean) {
  const p = selectedProvider.value
  if (!p) return
  aiApi.updateProvider(p.id, { enabled: v })
    .then(() => ElMessage.success(v ? '已启用' : '已停用'))
    .catch((e) => ElMessage.error(e?.message || '操作失败'))
    .finally(loadProviders)
}

function toggleLocalOnly(v: boolean) {
  const p = selectedProvider.value
  if (!p) return
  aiApi.updateProvider(p.id, { data_outbound: !v })
    .then(() => ElMessage.success(v ? '已开启不外发模式' : '已允许外发'))
    .catch((e) => ElMessage.error(e?.message || '操作失败'))
    .finally(loadProviders)
}

function openCreate() {
  editingId.value = null
  Object.assign(providerForm, { name: '', type: 'openai', endpoint: '', apiKey: '', model: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(p: AiProviderItem) {
  editingId.value = p.id
  Object.assign(providerForm, {
    name: p.name, type: p.type, endpoint: p.endpoint ?? '', apiKey: '',
    model: p.model ?? '', enabled: p.enabled,
  })
  dialogVisible.value = true
}

function submitProvider() {
  const payload: Record<string, unknown> = {
    name: providerForm.name.trim(),
    type: providerForm.type,
    endpoint: providerForm.endpoint.trim() || null,
    model: providerForm.model.trim() || null,
    enabled: providerForm.enabled,
  }
  if (providerForm.apiKey.trim()) payload.api_key = providerForm.apiKey.trim()
  if (!payload.name) { ElMessage.warning('请填写 Provider 名称'); return }
  saving.value = true
  const call = editingId.value
    ? aiApi.updateProvider(editingId.value, payload)
    : aiApi.createProvider(payload)
  call.then(() => {
    ElMessage.success(editingId.value ? 'Provider 已更新' : 'Provider 已创建')
    dialogVisible.value = false
    loadProviders()
  }).catch((e) => ElMessage.error(e?.message || '保存失败'))
    .finally(() => { saving.value = false })
}

function testProvider(p: AiProviderItem) {
  testingId.value = p.id
  aiApi.testProvider(p.id)
    .then((r) => {
      if (r.ok) {
        ElMessage.success(`连通正常：延迟 ${r.latency_ms}ms${r.reply ? `，回复「${r.reply}」` : ''}`)
      } else {
        ElMessage.error('连通失败')
      }
    })
    .catch((e) => ElMessage.error(e?.message || '连通失败'))
    .finally(() => { testingId.value = null })
}

function removeProvider(p: AiProviderItem) {
  ElMessageBox.confirm(`删除 Provider「${p.name}」？该操作不可恢复。`, '删除确认', { type: 'warning' })
    .then(() => aiApi.deleteProvider(p.id))
    .then(() => { ElMessage.success('已删除'); loadProviders() })
    .catch((e) => { if (e !== 'cancel') ElMessage.error(e?.message || '删除失败') })
}

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
  // LLM Provider 列表
  loadProviders()
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

.prov-list { display: flex; flex-direction: column; gap: 8px; }
.prov-row {
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.2s;
  &.active { border-color: var(--color-border-info); background: var(--color-background-info); }
}
.prov-head { display: flex; align-items: center; gap: 8px; }
.prov-name { font-size: 13px; font-weight: 600; }
.prov-model { font-size: 12px; color: var(--color-text-tertiary); }
.prov-meta {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 6px; font-size: 12px;
}
.prov-key { color: var(--color-text-secondary); font-family: monospace; }
.prov-usage { color: var(--color-text-tertiary); }
.prov-ops { margin-top: 6px; display: flex; justify-content: flex-end; gap: 2px; }
.prov-hint {
  margin-top: 10px; font-size: 11px; color: var(--color-text-tertiary);
  line-height: 1.6;
}

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
