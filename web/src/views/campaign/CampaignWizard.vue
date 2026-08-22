<template>
  <div class="page-container">
    <PageHeader title="发起新演练" :parents="['演练管理']">
      <template #actions>
        <el-button @click="$router.back()">取消</el-button>
      </template>
    </PageHeader>

    <div class="card" style="margin: 16px">
      <!-- 步骤条（demo 风格） -->
      <div class="wizard-steps">
        <template v-for="(s, i) in stepLabels" :key="i">
          <div class="step-item" :class="{ active: step >= i, done: step > i }" @click="i < step && (step = i)">
            <span class="step-num">{{ i + 1 }}</span>
            <span class="step-label">{{ s }}</span>
          </div>
          <div v-if="i < stepLabels.length - 1" class="step-line" :class="{ done: step > i }" />
        </template>
      </div>

      <!-- Step 1：基础设置 -->
      <template v-if="step === 0">
        <div class="form-group">
          <label class="form-label">演练名称<span class="required">*</span></label>
          <el-input v-model="form.name" placeholder="如：Q3全员防钓鱼演练" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">演练描述</label>
          <el-input v-model="form.description" type="textarea" :rows="3" class="form-input form-textarea"
            placeholder="简要描述本次演练的背景和目标..." />
        </div>
        <div class="form-group">
          <label class="form-label">演练类型<span class="required">*</span></label>
          <div class="option-grid cols-4">
            <div v-for="t in types" :key="t.value" class="option-card" :class="{ selected: form.type === t.value }"
              @click="form.type = t.value">
              <div class="option-card-header">
                <div class="option-card-icon" :style="{ background: t.color }">{{ t.icon }}</div>
                <div class="option-card-title">{{ t.label }}</div>
              </div>
              <p class="option-card-desc">{{ t.desc }}</p>
            </div>
          </div>
        </div>
      </template>

      <!-- Step 2：选择目标 -->
      <template v-else-if="step === 1">
        <div class="form-group">
          <label class="form-label">目标选择方式<span class="required">*</span></label>
          <div class="option-grid cols-3">
            <div class="option-card" :class="{ selected: targetMode === 'dept' }" @click="targetMode = 'dept'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#378ADD;">📁</div>
                <div class="option-card-title">按部门选择</div>
              </div>
              <p class="option-card-desc">从组织架构中选择</p>
            </div>
            <div class="option-card" :class="{ selected: targetMode === 'tag' }" @click="targetMode = 'tag'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#1D9E75;">🏷️</div>
                <div class="option-card-title">按标签/分组</div>
              </div>
              <p class="option-card-desc">如新员工组、高管组</p>
            </div>
            <div class="option-card" :class="{ selected: targetMode === 'csv' }" @click="targetMode = 'csv'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#7F77DD;">⬆️</div>
                <div class="option-card-title">导入CSV</div>
              </div>
              <p class="option-card-desc">上传人员名单文件</p>
            </div>
          </div>
        </div>

        <!-- 按部门选择 -->
        <div class="form-group" v-if="targetMode === 'dept'">
          <label class="form-label">组织架构（勾选父级自动包含子部门）</label>
          <div class="card dept-select-box">
            <el-tree
              ref="deptTreeRef"
              :data="deptTree"
              node-key="id"
              show-checkbox
              default-expand-all
              :props="{ label: 'label', children: 'children' }"
              @check="onDeptCheck"
            >
              <template #default="{ data }">
                <span class="tree-node-row">
                  <span>{{ data.label }}</span>
                  <el-tag size="small" effect="plain" style="margin-left:8px">{{ data.count }}</el-tag>
                </span>
              </template>
            </el-tree>
          </div>
          <p v-if="!deptTree.length" class="form-hint">组织架构加载失败，请稍后重试</p>
        </div>

        <!-- 按标签选择 -->
        <div class="form-group" v-else-if="targetMode === 'tag'">
          <label class="form-label">选择标签（可多选）</label>
          <div class="field-box">
            <label v-for="t in tagList" :key="t.id" class="field-item">
              <el-checkbox
                :model-value="checkedTagIds.includes(t.id)"
                @change="onTagCheck(t.id, $event)"
              />
              <span>{{ t.name }}（{{ t.user_count }} 人）</span>
            </label>
          </div>
          <p v-if="!tagList.length" class="form-hint">标签库为空，请先在「用户和组」页维护员工标签</p>
        </div>

        <!-- CSV 导入 -->
        <div class="form-group" v-else>
          <label class="form-label">上传人员名单 CSV（格式：工号,姓名,邮箱）</label>
          <el-upload
            drag
            action="#"
            :auto-upload="false"
            :show-file-list="false"
            accept=".csv"
            :on-change="onCsvChange"
            style="width: 100%"
          >
            <el-icon :size="36" color="var(--color-text-tertiary)"><UploadFilled /></el-icon>
            <div style="font-size:13px;margin-top:6px">拖拽 CSV 文件到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div style="font-size:11px;color:var(--color-text-tertiary)">自动识别邮箱列，未匹配平台员工档案的邮箱将被忽略</div>
            </template>
          </el-upload>
          <p v-if="csvEmails.length" class="form-hint">已解析 {{ csvEmails.length }} 个邮箱</p>
        </div>

        <!-- 已选目标汇总 -->
        <div class="form-group">
          <label class="form-label">
            已选目标 <span class="badge badge-info">共 {{ targetCount.toLocaleString() }} 人</span>
          </label>
          <div class="selected-tags-box">
            <span
              v-for="t in selectedTargets"
              :key="t.key"
              class="badge"
              :style="`background:${t.color}22;color:${t.color};`"
            >
              {{ t.label }} ({{ t.count.toLocaleString() }})
              <span style="margin-left:4px;cursor:pointer" @click="t.remove()">✕</span>
            </span>
            <span v-if="!selectedTargets.length" class="form-hint">尚未选择目标</span>
          </div>
        </div>

        <!-- 授权确认（红线：无授权不可启动） -->
        <div class="form-group">
          <el-checkbox v-model="authConfirmed">
            我已获得企业充分授权，仅对自有员工开展模拟钓鱼演练（教育为主，数据严格保密，演练数据按留存策略处置）
          </el-checkbox>
        </div>
      </template>

      <!-- Step 3：选择模板 -->
      <template v-else-if="step === 2">
        <div class="form-group">
          <label class="form-label">邮件模板<span class="required">*</span></label>
          <div class="option-grid cols-4">
            <div v-for="(tpl) in templates" :key="tpl.id" class="template-card"
              :class="{ selected: tplForm.template_id === tpl.id }" @click="tplForm.template_id = tpl.id">
              <div class="template-preview" :style="{ color: tpl.color }">
                <svg v-if="tpl.icon === 'mail'" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                <svg v-else-if="tpl.icon === 'oa'" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
                <svg v-else-if="tpl.icon === 'gift'" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                <svg v-else width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </div>
              <div class="template-meta">
                <p class="template-name">{{ tpl.subject }}</p>
                <span class="template-tag">{{ tpl.scene }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">发件人伪装名称<span class="required">*</span></label>
            <el-input v-model="tplForm.sender_name" class="form-input" />
            <p class="form-hint">员工邮箱中显示的发件人名称</p>
          </div>
          <div class="form-group">
            <label class="form-label">欺骗性域名<span class="required">*</span></label>
            <el-select v-model="tplForm.spoof_domain" class="form-input">
              <el-option
                v-for="d in spoofDomains"
                :key="d.id"
                :label="d.domain"
                :value="d.domain"
              />
            </el-select>
            <p class="form-hint">{{ domainDnsHint }}</p>
          </div>
        </div>
      </template>

      <!-- Step 4：落地页 -->
      <template v-else-if="step === 3">
        <div class="form-group">
          <label class="form-label">钓鱼落地页<span class="required">*</span></label>
          <div class="option-grid cols-3">
            <div v-for="lp in landingPages" :key="lp.id" class="template-card"
              :class="{ selected: landingForm.page_id === lp.id }" @click="landingForm.page_id = lp.id">
              <div class="landing-preview" :style="{ background: lp.bg }">
                <span style="font-size:11px;color:#378ADD;font-weight:500;">{{ lp.label }}</span>
              </div>
              <div class="template-meta">
                <p class="template-name">{{ lp.name }}</p>
                <span class="template-tag">{{ lp.tag }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">数据收集表单配置</label>
          <div class="field-box">
            <label v-for="f in fieldOptions" :key="f.val" class="field-item">
              <el-checkbox v-model="f.checked" />
              <span>{{ f.label }}</span>
            </label>
          </div>
          <p class="form-hint">💡 教育弹窗提示一旦用户输入密码后立即显示："这是一次演练，您刚才差点泄露了密码！"</p>
        </div>
      </template>

      <!-- Step 5：发送配置 -->
      <template v-else-if="step === 4">
        <div class="form-group">
          <label class="form-label">选择发送配置方案<span class="required">*</span></label>
          <p class="form-hint" style="margin-bottom:12px;">从已配置的 SMTP 通道中选择，如需新增或修改请前往「发送配置」页</p>
          <div class="option-grid cols-2">
            <div
              v-for="ch in sendChannels"
              :key="ch.id"
              class="option-card"
              :class="{ selected: sendChannelId === ch.id }"
              @click="sendChannelId = ch.id"
            >
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#378ADD;">📧</div>
                <div class="option-card-title">{{ ch.name }}</div>
                <span v-if="ch.is_default" class="badge badge-info" style="margin-left:auto;">默认</span>
                <span
                  v-else
                  class="badge"
                  :class="ch.status === 'ok' ? 'badge-success' : 'badge-warning'"
                  style="margin-left:auto;"
                >{{ ch.status === 'ok' ? '运行中' : '异常' }}</span>
              </div>
              <div class="send-meta">
                <div>🖥️ SMTP：{{ ch.server || '-' }}:{{ ch.port || '-' }}</div>
                <div>🔐 加密：{{ ch.ssl ? 'SSL/TLS' : 'STARTTLS' }}</div>
                <div>📦 每日上限：{{ ch.daily_limit.toLocaleString() }} 封</div>
                <div>📊 送达评分：{{ ch.score }} 分 · 最近测试：{{ ch.last_test }}</div>
                <div class="dns-badges" v-if="selectedDomain">
                  <span class="badge" :class="selectedDomain.spf === 'OK' ? 'badge-success' : 'badge-warning'">SPF {{ selectedDomain.spf === 'OK' ? '✓' : '✗' }}</span>
                  <span class="badge" :class="selectedDomain.dkim === 'OK' ? 'badge-success' : 'badge-warning'">DKIM {{ selectedDomain.dkim === 'OK' ? '✓' : '✗' }}</span>
                  <span class="badge" :class="selectedDomain.dmarc === 'OK' ? 'badge-success' : 'badge-warning'">DMARC {{ selectedDomain.dmarc === 'OK' ? '✓' : '✗' }}</span>
                </div>
              </div>
            </div>
          </div>
          <p v-if="!sendChannels.length" class="form-hint">暂无可用的 SMTP 通道，请先在「发送配置」页添加</p>
        </div>
        <div class="form-group">
          <label class="form-label">送达率预估</label>
          <div class="deliver-box">
            <div class="deliver-ring">
              <div class="deliver-ring-inner">{{ selectedChannel?.score ?? 0 }}</div>
            </div>
            <div class="deliver-info">
              <div style="font-size:12px;font-weight:500;">送达评分：{{ selectedChannel?.score ?? 0 }} 分</div>
              <div style="font-size:11px;color:var(--color-text-secondary);margin-top:2px;">{{ domainDnsHint }}</div>
            </div>
            <span class="badge" :class="(selectedChannel?.score ?? 0) >= 80 ? 'badge-success' : 'badge-warning'">{{ (selectedChannel?.score ?? 0) >= 80 ? '优秀' : '待检测' }}</span>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">发送测试（可选）</label>
          <div class="test-row">
            <el-input v-model="sendForm.test_email" placeholder="输入测试接收邮箱..." class="form-input" />
            <el-button type="primary" :loading="wizardTestLoading" @click="sendWizardTest">发送测试</el-button>
          </div>
          <p v-if="testResult" class="form-hint" :style="{ color: testResult.startsWith('✓') ? '#1D9E75' : '#D85A30' }">{{ testResult }}</p>
        </div>
        <div class="info-tip">
          ℹ️ <span>如需配置新的SMTP服务器、域名或DNS记录，请前往 <el-link type="primary" :underline="false" style="font-size:11px;" @click="router.push('/send-config')">发送配置</el-link></span>
        </div>
      </template>

      <!-- Step 6：触发机制 -->
      <template v-else-if="step === 5">
        <div class="form-group">
          <label class="form-label">发送时机<span class="required">*</span></label>
          <div class="option-grid cols-2">
            <div class="option-card" :class="{ selected: triggerForm.mode === 'schedule' }" @click="triggerForm.mode = 'schedule'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#378ADD;">⏰</div>
                <div class="option-card-title">定时发送</div>
              </div>
              <p class="option-card-desc">在指定时间统一发送</p>
            </div>
            <div class="option-card" :class="{ selected: triggerForm.mode === 'now' }" @click="triggerForm.mode = 'now'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#1D9E75;">⚡</div>
                <div class="option-card-title">立即发送</div>
              </div>
              <p class="option-card-desc">启动后立即开始</p>
            </div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">发送开始时间</label>
            <el-input v-model="triggerForm.schedule_time" class="form-input" placeholder="2026-08-20 09:30" />
          </div>
          <div class="form-group">
            <label class="form-label">分批次策略</label>
            <el-select v-model="triggerForm.batch" class="form-input">
              <el-option label="分 3 批间隔 30 分钟" value="3-30" />
              <el-option label="分 5 批间隔 15 分钟" value="5-15" />
              <el-option label="不分批，统一发送" value="none" />
            </el-select>
            <p class="form-hint">分批次可防拥堵、防网关识别</p>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">高级防识别设置</label>
          <div class="field-box">
            <label class="field-item" style="opacity:.55">
              <el-checkbox v-model="triggerForm.adv[0]" disabled />
              <span>邮件内容随机化（防止垃圾网关识别）</span>
              <el-tag size="small" type="info" effect="plain">三期</el-tag>
            </label>
            <label class="field-item" style="opacity:.55">
              <el-checkbox v-model="triggerForm.adv[1]" disabled />
              <span>随机发件时间抖动（±5分钟）</span>
              <el-tag size="small" type="info" effect="plain">三期</el-tag>
            </label>
            <label class="field-item">
              <el-checkbox v-model="triggerForm.adv[2]" />
              <span>开启追踪像素降级模式（图片替代）</span>
            </label>
          </div>
        </div>
      </template>

      <!-- Step 7：培训跳转 -->
      <template v-else-if="step === 6">
        <div class="form-group">
          <label class="form-label">中招后处理方式<span class="required">*</span></label>
          <div class="option-grid cols-2">
            <div class="option-card" :class="{ selected: trainForm.mode === 'train' }" @click="trainForm.mode = 'train'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#1D9E75;">✅</div>
                <div class="option-card-title">立即跳转培训</div>
              </div>
              <p class="option-card-desc">推荐：中招即学，印象深刻</p>
            </div>
            <div class="option-card" :class="{ selected: trainForm.mode === 'popup' }" @click="trainForm.mode = 'popup'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#EF9F27;">ℹ️</div>
                <div class="option-card-title">仅显示教育弹窗</div>
              </div>
              <p class="option-card-desc">显示警示信息后关闭</p>
            </div>
            <div class="option-card" :class="{ selected: trainForm.mode === 'url' }" @click="trainForm.mode = 'url'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#378ADD;">🔗</div>
                <div class="option-card-title">跳转到指定页面</div>
              </div>
              <p class="option-card-desc">自定义跳转目标（如安全知识库）</p>
            </div>
            <div class="option-card" :class="{ selected: trainForm.mode === 'none' }" @click="trainForm.mode = 'none'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#8c8c8c;">🚫</div>
                <div class="option-card-title">不强制处理</div>
              </div>
              <p class="option-card-desc">仅记录数据，不做任何提示</p>
            </div>
          </div>
        </div>
        <div v-if="trainForm.mode === 'url'" class="form-group">
          <label class="form-label">跳转页面地址<span class="required">*</span></label>
          <el-input v-model="trainForm.redirect_url" class="form-input"
            placeholder="https://company.com/security/knowledge-base" />
          <p class="form-hint">仅支持 http/https，提交后员工将被 302 重定向到该页面（不经过教育弹窗）</p>
        </div>
        <div class="form-group">
          <label class="form-label">关联培训课程</label>
          <el-select v-model="trainForm.course_id" class="form-input">
            <el-option v-for="c in courses" :key="c.id" :label="`${c.title}(${c.duration_min}分钟)`" :value="String(c.id)" />
          </el-select>
        </div>
        <div class="form-group">
          <label class="form-label">强制培训触发条件</label>
          <div class="field-box">
            <label class="field-item">
              <el-checkbox v-model="trainForm.rule[0]" />
              <span>点击链接 → 自动下发培训任务</span>
            </label>
            <label class="field-item">
              <el-checkbox v-model="trainForm.rule[1]" />
              <span>输入密码 → 自动下发培训 + 考试</span>
            </label>
            <label class="field-item">
              <el-checkbox v-model="trainForm.rule[2]" />
              <span>3 次以上中招者 → 升级至高管组通知</span>
            </label>
          </div>
        </div>

        <div class="summary-box">
          <p class="summary-title">📋 配置确认清单</p>
          <div class="summary-grid">
            <div v-for="row in summaryRows" :key="row.key">
              {{ row.key }}：<strong>{{ row.val }}</strong>
            </div>
            <div>合规状态：<span style="color:#1D9E75;">✓ 已勾选授权</span></div>
          </div>
        </div>
      </template>

      <!-- footer -->
      <div class="wizard-footer">
        <span class="wizard-progress">第 {{ step + 1 }} 步 / 共 7 步</span>
        <div class="footer-btns">
          <el-button :disabled="step === 0" @click="step--">上一步</el-button>
          <el-button v-if="step < 6" type="primary" @click="nextStep">下一步 →</el-button>
          <el-button v-else type="primary" @click="submit">✓ 确认发起演练</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElLink } from 'element-plus'
import type { ElTree, UploadFile } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import { campaignApi, orgApi, templateApi, channelApi, trainingApi } from '@/api'

const router = useRouter()
const step = ref(0)
const stepLabels = ['基础设置', '选择目标', '选择模板', '落地页', '发送配置', '触发机制', '培训跳转']

const form = reactive({
  name: 'Q3全员防钓鱼演练',
  description: '针对Q3全员安全意识提升计划，开展全公司范围的邮件钓鱼演练，重点考察员工对财务类钓鱼邮件的识别能力。',
  type: 'mail' as 'mail' | 'sms' | 'social' | 'usb',
})
const types = [
  { value: 'mail' as const, label: '邮件钓鱼', desc: '最常用，覆盖率高', color: '#378ADD', icon: '📧' },
  { value: 'sms' as const, label: '短信钓鱼', desc: '移动端场景', color: '#1D9E75', icon: '💬' },
  { value: 'social' as const, label: '社交媒体', desc: '微信/企微场景', color: '#EF9F27', icon: '👥' },
  { value: 'usb' as const, label: 'USB实物', desc: '实地投放测试', color: '#7F77DD', icon: '⚡' },
]

// ============ 目标选择 ============
const targetMode = ref<'dept' | 'tag' | 'csv'>('dept')

interface DeptNode { id: number; label: string; count: number; children?: DeptNode[] }
interface TagRow { id: number; name: string; color: string; user_count: number }

const deptTree = ref<DeptNode[]>([])
const tagList = ref<TagRow[]>([])
const deptTreeRef = ref<InstanceType<typeof ElTree>>()
/** 勾选的叶子部门（父级勾选由树级联，叶子计数不重复） */
const checkedLeafDeptIds = ref<number[]>([])
const checkedTagIds = ref<number[]>([])
const csvEmails = ref<string[]>([])
const authConfirmed = ref(false)

onMounted(() => {
  orgApi.deptTree()
    .then((list) => { if (Array.isArray(list)) deptTree.value = list as DeptNode[] })
    .catch(() => ElMessage.warning('组织架构加载失败，请稍后重试'))
  orgApi.tags()
    .then((list) => { if (Array.isArray(list)) tagList.value = list as TagRow[] })
    .catch(() => {})
  trainingApi.courses()
    .then((list) => { if (Array.isArray(list)) courses.value = list as { id: number; title: string; duration_min: number }[] })
    .catch(() => {})
  loadWizardAssets()
})

// 部门树扁平映射：id → {label, count}
const deptMap = computed(() => {
  const m = new Map<number, { label: string; count: number }>()
  const walk = (nodes: DeptNode[]) => {
    for (const n of nodes) {
      m.set(n.id, { label: n.label, count: n.count })
      if (n.children?.length) walk(n.children)
    }
  }
  walk(deptTree.value)
  return m
})

function onDeptCheck() {
  // 只收集叶子节点（含父级级联勾选的叶子），人数按叶子累加不重复
  const leaves: number[] = []
  const walk = (nodes: DeptNode[]) => {
    for (const n of nodes) {
      if (n.children?.length) walk(n.children)
      else leaves.push(n.id)
    }
  }
  walk(deptTree.value)
  const checked = new Set((deptTreeRef.value?.getCheckedKeys(true) || []) as number[])
  checkedLeafDeptIds.value = leaves.filter((id) => checked.has(id))
}

function onTagCheck(id: number, checked: boolean | string | number) {
  const on = checked === true
  checkedTagIds.value = on
    ? [...checkedTagIds.value.filter((x) => x !== id), id]
    : checkedTagIds.value.filter((x) => x !== id)
}

function onCsvChange(file: UploadFile) {
  const raw = file.raw
  if (!raw) return
  const reader = new FileReader()
  reader.onload = () => {
    const text = String(reader.result || '')
    const emails = new Set<string>()
    for (const line of text.split(/\r?\n/)) {
      if (!line.trim()) continue
      for (const cell of line.split(/[,;\t]/)) {
        const hit = cell.trim().toLowerCase().match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)
        if (hit) emails.add(hit[0])
      }
    }
    csvEmails.value = [...emails]
    if (emails.size) ElMessage.success(`已解析 ${emails.size} 个邮箱`)
    else ElMessage.warning('未在文件中识别到邮箱列（格式：工号,姓名,邮箱）')
  }
  reader.readAsText(raw)
}

interface TargetChip { key: string; label: string; count: number; color: string; remove: () => void }

const selectedTargets = computed<TargetChip[]>(() => {
  const chips: TargetChip[] = []
  for (const id of checkedLeafDeptIds.value) {
    const d = deptMap.value.get(id)
    if (d) chips.push({ key: `dept-${id}`, label: d.label, count: d.count, color: '#378ADD',
      remove: () => { deptTreeRef.value?.setChecked(id, false, false); onDeptCheck() } })
  }
  for (const id of checkedTagIds.value) {
    const t = tagList.value.find((x) => x.id === id)
    if (t) chips.push({ key: `tag-${id}`, label: t.name, count: t.user_count, color: '#1D9E75',
      remove: () => { checkedTagIds.value = checkedTagIds.value.filter((x) => x !== id) } })
  }
  if (csvEmails.value.length) {
    chips.push({ key: 'csv', label: 'CSV名单', count: csvEmails.value.length, color: '#7F77DD',
      remove: () => { csvEmails.value = [] } })
  }
  return chips
})

const targetCount = computed(() =>
  selectedTargets.value.reduce((sum, t) => sum + t.count, 0),
)

/** 模板/落地页/域名/发送通道全部来自素材库与发送配置（接口加载） */
const templateColors = ['#378ADD', '#1D9E75', '#EF9F27', '#7F77DD']
const sceneIconMap: Record<string, string> = {
  upgrade: 'oa', system: 'oa', finance: 'mail', lottery: 'gift',
  holiday: 'gift', hr: 'user', alert: 'mail', prize: 'gift', security: 'mail',
}
const landingBgPalette = [
  'linear-gradient(135deg,#378ADD22,#1D9E7522)',
  'linear-gradient(135deg,#EF9F2722,#D85A3022)',
  'linear-gradient(135deg,#7F77DD22,#378ADD22)',
  'linear-gradient(135deg,#0D948822,#378ADD22)',
]

const templates = ref<{ id: number; subject: string; scene: string; color: string; icon: string; sender?: string }[]>([])
const landingPages = ref<{ id: number; name: string; tag: string; label: string; bg: string }[]>([])
const spoofDomains = ref<{ id: number; domain: string; spf: string; dkim: string; dmarc: string }[]>([])
const sendChannels = ref<{ id: number; name: string; type: string; type_label: string; server?: string; port?: number; ssl?: boolean; daily_limit: number; score: number; status: string; is_default?: boolean; last_test?: string }[]>([])

const tplForm = reactive({
  template_id: 0 as number,
  sender_name: '',
  spoof_domain: '',
})

async function loadWizardAssets() {
  try {
    const list = (await templateApi.emailTemplates()) as {
      id: number; subject: string; catText: string; cat: string; sender?: string
    }[]
    if (Array.isArray(list) && list.length) {
      templates.value = list.map((t, i) => ({
        id: t.id,
        subject: t.subject,
        scene: t.catText || t.cat,
        color: templateColors[i % templateColors.length],
        icon: sceneIconMap[t.cat] || 'mail',
        sender: t.sender,
      }))
      const first = templates.value[0]
      if (!tplForm.template_id && first) {
        tplForm.template_id = first.id
        tplForm.sender_name = first.sender || ''
      }
    }
  } catch {
    ElMessage.warning('邮件模板加载失败，请稍后在「素材模板」页确认模板状态')
  }
  try {
    const list = (await templateApi.landingPages()) as {
      id: number; name: string; typeText: string
    }[]
    if (Array.isArray(list) && list.length) {
      landingPages.value = list.map((p, i) => ({
        id: p.id,
        name: p.name,
        tag: p.typeText,
        label: p.name,
        bg: landingBgPalette[i % landingBgPalette.length],
      }))
      if (!landingForm.page_id && landingPages.value.length) landingForm.page_id = landingPages.value[0].id
    }
  } catch {
    ElMessage.warning('落地页加载失败，请稍后在「素材模板」页确认')
  }
  try {
    const list = (await channelApi.domains()) as { id: number; domain: string; spf: string; dkim: string; dmarc: string }[]
    if (Array.isArray(list) && list.length) {
      spoofDomains.value = list
      if (!tplForm.spoof_domain && list[0]) tplForm.spoof_domain = list[0].domain
    }
  } catch { /* 域名加载失败不阻断 */ }
  try {
    const list = (await channelApi.list()) as typeof sendChannels.value
    if (Array.isArray(list)) {
      sendChannels.value = list.filter((ch) => ch.type === 'smtp')
      if (!sendChannelId.value && sendChannels.value.length) sendChannelId.value = sendChannels.value[0].id
    }
  } catch { /* 通道加载失败不阻断 */ }
}

const selectedDomain = computed(() =>
  spoofDomains.value.find((d) => d.domain === tplForm.spoof_domain),
)
const domainDnsHint = computed(() => {
  const d = selectedDomain.value
  if (!d) return 'DNS 状态未知'
  const parts = [`SPF ${d.spf}`, `DKIM ${d.dkim}`, `DMARC ${d.dmarc}`]
  return parts.join(' · ')
})
const fieldOptions = ref([
  { val: 'account', label: '收集用户名/邮箱', checked: true },
  { val: 'password', label: '收集登录密码（不存储明文）', checked: true },
  { val: 'sms_code', label: '收集手机验证码输入行为', checked: false },
  { val: 'attach', label: '触发附件下载（可选载荷）', checked: false },
])
const landingForm = reactive({ page_id: 1 })

const sendChannelId = ref(0) // 选中的 SMTP 发送通道 id
const selectedChannel = computed(() =>
  sendChannels.value.find((ch) => ch.id === sendChannelId.value),
)
const sendForm = reactive({ test_email: '' })
const testResult = ref('')
const wizardTestLoading = ref(false)

/** 向导内发送测试：走所选 SMTP 通道真实发信 */
async function sendWizardTest() {
  const to = sendForm.test_email.trim()
  if (!to || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) {
    ElMessage.warning('请填写正确的测试接收邮箱')
    return
  }
  if (!sendChannelId.value) {
    ElMessage.warning('请先选择发送通道')
    return
  }
  wizardTestLoading.value = true
  testResult.value = ''
  try {
    // 按所选模板 + 落地页 + 伪装发件人发送真实样式预览邮件
    const res = await channelApi.sendTestEmailWithContent(sendChannelId.value, {
      to,
      template_id: tplForm.template_id || undefined,
      landing_page_id: landingForm.page_id || undefined,
      sender_name: tplForm.sender_name || undefined,
      domain: tplForm.spoof_domain || undefined,
    })
    testResult.value = res.ok ? `✓ ${res.message}` : `✗ ${res.message}`
    if (res.ok) ElMessage.success('测试邮件已发送（含所选模板与落地页链接）')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    wizardTestLoading.value = false
  }
}

const triggerForm = reactive({
  mode: 'schedule' as 'schedule' | 'now',
  schedule_time: '2026-08-20 09:30',
  batch: '3-30',
  adv: [true, true, false],
})

const trainForm = reactive({
  mode: 'train' as 'train' | 'popup' | 'none' | 'url',
  course_id: '1',
  redirect_url: '',
  rule: [true, true, false],
})

// 培训课程库（redirect 落点 /learn/{course_id} 按真实课程渲染）
const courses = ref<{ id: number; title: string; duration_min: number }[]>([])

const summaryRows = computed(() => [
  { key: '演练名称', val: form.name },
  { key: '演练类型', val: types.find(t => t.value === form.type)?.label || '邮件钓鱼' },
  { key: '目标人数', val: `${targetCount.value.toLocaleString()} 人` },
  { key: '邮件模板', val: templates.value.find(t => t.id === tplForm.template_id)?.subject || '-' },
  { key: '落地页', val: landingPages.value.find(p => p.id === landingForm.page_id)?.name || '-' },
  { key: '发送配置', val: sendChannels.value.find((ch) => ch.id === sendChannelId.value)?.name || '-' },
  { key: '发送时间', val: triggerForm.mode === 'schedule' ? `${triggerForm.schedule_time}（分3批）` : '立即发送' },
  {
    key: '培训设置',
    val: trainForm.mode === 'train'
      ? `立即跳转${courses.value.find(c => c.id === Number(trainForm.course_id))?.title ?? ''}`
      : trainForm.mode === 'url'
        ? `跳转指定页面：${trainForm.redirect_url || '-'}`
        : trainForm.mode === 'popup' ? '仅显示教育弹窗' : '不强制处理',
  },
])

/** 下一步：步骤 2 需校验目标与授权勾选（红线） */
function nextStep() {
  if (step.value === 1) {
    if (!targetCount.value) {
      ElMessage.warning('请先选择演练目标（部门/标签/CSV）')
      return
    }
    if (!authConfirmed.value) {
      ElMessage.warning('请勾选授权确认（未获得授权不可发起演练）')
      return
    }
  }
  step.value++
}

/** 目标来源模式：多来源并选时传 mix */
function buildTargetMode(): 'dept' | 'tag' | 'csv' | 'mix' {
  const sources = [checkedLeafDeptIds.value.length, checkedTagIds.value.length, csvEmails.value.length]
    .filter((n) => n > 0).length
  if (sources > 1) return 'mix'
  if (checkedLeafDeptIds.value.length) return 'dept'
  if (checkedTagIds.value.length) return 'tag'
  return 'csv'
}

async function submit() {
  if (!targetCount.value) {
    ElMessage.warning('请先选择演练目标')
    return
  }
  if (!authConfirmed.value) {
    ElMessage.warning('请勾选授权确认（未获得授权不可发起演练）')
    return
  }
  try {
    await campaignApi.create({
      ...form,
      target_mode: buildTargetMode(),
      target_snapshot: {
        dept_ids: checkedLeafDeptIds.value,
        tag_ids: checkedTagIds.value,
        emails: csvEmails.value,
      },
      template_id: tplForm.template_id,
      landing_page_id: landingForm.page_id,
      channel_id: sendChannelId.value || null,
      domain_id: selectedDomain.value?.id || null,
      schedule_type: triggerForm.mode === 'now' ? 'now' : 'timed',
      schedule_at: triggerForm.mode === 'schedule' ? triggerForm.schedule_time : null,
      batch_count: 3,
      pixel_degrade: triggerForm.adv[2],
      // 前端 mode：train/popup/none/url；后端 policy：redirect/popup/none/url（train→redirect 映射）
      training_policy: trainForm.mode === 'train' ? 'redirect' : trainForm.mode,
      training_redirect_url: trainForm.mode === 'url' ? trainForm.redirect_url.trim() : '',
      course_ids: trainForm.mode === 'train' ? [Number(trainForm.course_id)] : [],
      auth_confirmed: true,
    })
    ElMessage.success(`演练创建成功，目标 ${targetCount.value.toLocaleString()} 人已展开`)
    router.push('/campaign')
  } catch {
    // 失败提示由 http 拦截器统一弹出，停留本页便于修改后重试
  }
}
</script>

<style scoped lang="scss">
/* ========== Wizard Steps ========== */
.wizard-steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: default;
  &.done { cursor: pointer; }
}
.step-num {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--color-background-tertiary);
  color: var(--color-text-tertiary);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600;
  flex-shrink: 0;
  transition: all .2s;
}
.step-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}
.step-item.active .step-num {
  background: var(--color-primary);
  color: #fff;
}
.step-item.active .step-label {
  color: var(--color-text-primary);
  font-weight: 500;
}
.step-item.done .step-num {
  background: #1D9E75;
  color: #fff;
}
.step-item.done .step-label {
  color: var(--color-text-secondary);
}
.step-line {
  flex: 1;
  height: 2px;
  background: var(--color-background-tertiary);
  margin: 0 6px;
  &.done { background: #1D9E75; }
}

/* ========== Form ========== */
.form-group {
  margin-bottom: 18px;
}
.form-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}
.required {
  color: #a32d2d;
  margin-left: 2px;
}
.form-input {
  width: 100%;
}
.form-textarea {
  resize: none;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* ========== Option Card ========== */
.option-grid {
  display: grid;
  gap: 10px;
  &.cols-2 { grid-template-columns: 1fr 1fr; }
  &.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
  &.cols-4 { grid-template-columns: repeat(4, 1fr); }
}
.option-card {
  border: 1.5px solid var(--color-border-tertiary);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all .2s;
  background: var(--color-background-primary);
  &.selected {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px rgba(55,138,221,0.1);
  }
}
.option-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.option-card-icon {
  width: 34px; height: 34px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  font-size: 14px;
  flex-shrink: 0;
}
.option-card-title {
  font-size: 13px;
  font-weight: 500;
}
.option-card-desc {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 8px 0 0 0;
}

/* ========== Template Card ========== */
.template-card {
  border: 1.5px solid var(--color-border-tertiary);
  border-radius: 8px;
  cursor: pointer;
  overflow: hidden;
  transition: all .2s;
  background: var(--color-background-primary);
  &.selected {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px rgba(55,138,221,0.1);
  }
}
.template-preview {
  height: 84px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-background-secondary);
  border-bottom: 0.5px solid var(--color-border-tertiary);
}
.landing-preview {
  height: 84px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 0.5px solid var(--color-border-tertiary);
}
.template-meta {
  padding: 8px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}
.template-name {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.template-tag {
  font-size: 10px;
  color: var(--color-text-secondary);
  padding: 2px 6px;
  background: var(--color-background-secondary);
  border-radius: 4px;
  flex-shrink: 0;
}

/* ========== Target ========== */
.selected-tags-box {
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  padding: 12px;
  background: var(--color-background-secondary);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.dept-select-box {
  max-height: 320px;
  overflow-y: auto;
  :deep(.el-tree) { background: transparent; }
}
.tree-node-row {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
}
.badge-add {
  color: var(--color-text-secondary);
  border: 1px dashed var(--color-border-tertiary);
  background: var(--color-background-primary);
  cursor: pointer;
}

/* ========== Field Box ========== */
.field-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  background: var(--color-background-secondary);
}
.field-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-primary);
  cursor: pointer;
}

/* ========== Send Config ========== */
.send-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.8;
  margin-top: 6px;
  strong {
    color: var(--color-text-primary);
    font-weight: 500;
  }
}
.dns-badges {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}
.deliver-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  background: var(--color-background-secondary);
}
.deliver-ring {
  width: 48px; height: 48px;
  border-radius: 50%;
  background: conic-gradient(#1D9E75 0% 98%, #e5e7eb 98% 100%);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.deliver-ring-inner {
  width: 38px; height: 38px;
  border-radius: 50%;
  background: var(--color-background-secondary);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
  color: #1D9E75;
}
.deliver-info {
  flex: 1;
  min-width: 0;
}
.test-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.info-tip {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(55,138,221,0.06);
  border: 1px dashed rgba(55,138,221,0.3);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* ========== Badges ========== */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.badge-info { background: rgba(55,138,221,0.15); color: #378ADD; }
.badge-success { background: rgba(29,158,117,0.15); color: #1D9E75; }
.badge-warning { background: rgba(239,159,39,0.15); color: #EF9F27; }

/* ========== Summary ========== */
.summary-box {
  margin-top: 20px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(29,158,117,0.07);
  border: 1px dashed rgba(29,158,117,0.4);
}
.summary-title {
  font-size: 13px;
  font-weight: 500;
  color: #1D9E75;
  margin: 0 0 12px 0;
}
.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
  strong {
    color: var(--color-text-primary);
    font-weight: 500;
  }
}

/* ========== Footer ========== */
.wizard-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-tertiary);
}
.wizard-progress {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.footer-btns {
  display: flex;
  gap: 8px;
}
</style>
