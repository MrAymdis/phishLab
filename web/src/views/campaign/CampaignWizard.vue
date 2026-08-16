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
        <div class="form-group">
          <label class="form-label">
            已选目标 <span class="badge badge-info">共 3,580 人</span>
          </label>
          <div class="selected-tags-box">
            <span class="badge" style="background:#378ADD22;color:#378ADD;">全公司 (3,580) <span style="margin-left:4px;cursor:pointer">✕</span></span>
            <span class="badge" style="background:#1D9E7522;color:#1D9E75;">研发部 (420) <span style="margin-left:4px;cursor:pointer">✕</span></span>
            <span class="badge" style="background:#EF9F2722;color:#EF9F27;">新员工组 (30) <span style="margin-left:4px;cursor:pointer">✕</span></span>
            <span class="badge badge-add">+ 添加部门</span>
          </div>
          <p class="form-hint">⚠️ 请确认已获得充分授权对上述人员开展钓鱼演练，相关数据将严格保密</p>
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
              <el-option label="finance-company-notice.com" value="finance-company-notice.com" />
              <el-option label="oa-system-update.cn" value="oa-system-update.cn" />
              <el-option label="hr-benefits-claim.com" value="hr-benefits-claim.com" />
            </el-select>
            <p class="form-hint">SPF/DKIM已配置 ✓</p>
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
          <p class="form-hint" style="margin-bottom:12px;">从已配置的发送方案中选择，如需新增或修改请前往「素材模板 → 发件配置管理」</p>
          <div class="option-grid cols-2">
            <div class="option-card" :class="{ selected: sendForm.profile === 'default' }" @click="sendForm.profile = 'default'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#378ADD;">📧</div>
                <div class="option-card-title">平台默认SMTP</div>
                <span class="badge badge-info" style="margin-left:auto;">默认</span>
              </div>
              <div class="send-meta">
                <div>📧 发件域名：<strong>finance-company-notice.com</strong></div>
                <div>🖥️ SMTP：smtp.phish-platform.com:587</div>
                <div>📦 每日上限：5,000 封</div>
                <div class="dns-badges">
                  <span class="badge badge-success">SPF ✓</span>
                  <span class="badge badge-success">DKIM ✓</span>
                  <span class="badge badge-success">DMARC ✓</span>
                </div>
              </div>
            </div>
            <div class="option-card" :class="{ selected: sendForm.profile === 'custom' }" @click="sendForm.profile = 'custom'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#7F77DD;">🖥️</div>
                <div class="option-card-title">企业自建SMTP</div>
              </div>
              <div class="send-meta">
                <div>📧 发件域名：<strong>oa-system-update.cn</strong></div>
                <div>🖥️ SMTP：mail.company.com:465</div>
                <div>📦 每日上限：10,000 封</div>
                <div class="dns-badges">
                  <span class="badge badge-success">SPF ✓</span>
                  <span class="badge badge-success">DKIM ✓</span>
                  <span class="badge badge-warning">DMARC ✗</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">送达率预估</label>
          <div class="deliver-box">
            <div class="deliver-ring">
              <div class="deliver-ring-inner">98%</div>
            </div>
            <div class="deliver-info">
              <div style="font-size:12px;font-weight:500;">邮件送达率：98%</div>
              <div style="font-size:11px;color:var(--color-text-secondary);margin-top:2px;">DNS三项记录均已配置，不易被网关拦截</div>
            </div>
            <span class="badge badge-success">优秀</span>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">发送测试（可选）</label>
          <div class="test-row">
            <el-input v-model="sendForm.test_email" placeholder="输入测试接收邮箱..." class="form-input" />
            <el-button type="primary" @click="testResult = 'ok'">发送测试</el-button>
          </div>
        </div>
        <div class="info-tip">
          ℹ️ <span>如需配置新的SMTP服务器、域名或DNS记录，请前往 <el-link type="primary" :underline="false" style="font-size:11px;">素材模板 → 发件配置管理</el-link></span>
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
            <label class="field-item">
              <el-checkbox v-model="triggerForm.adv[0]" />
              <span>邮件内容随机化（防止垃圾网关识别）</span>
            </label>
            <label class="field-item">
              <el-checkbox v-model="triggerForm.adv[1]" />
              <span>随机发件时间抖动（±5分钟）</span>
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
          <div class="option-grid cols-3">
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
            <div class="option-card" :class="{ selected: trainForm.mode === 'none' }" @click="trainForm.mode = 'none'">
              <div class="option-card-header">
                <div class="option-card-icon" style="background:#8c8c8c;">🚫</div>
                <div class="option-card-title">不强制处理</div>
              </div>
              <p class="option-card-desc">仅记录数据，不做任何提示</p>
            </div>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">关联培训课程</label>
          <el-select v-model="trainForm.course_id" class="form-input">
            <el-option label="《钓鱼邮件识别与防范》(15分钟)" value="1" />
            <el-option label="《全员信息安全意识》(30分钟)" value="2" />
            <el-option label="《财务人员专项安全课》(25分钟)" value="3" />
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
          <el-button v-if="step < 6" type="primary" @click="step++">下一步 →</el-button>
          <el-button v-else type="primary" @click="submit">✓ 确认发起演练</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElLink } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import { campaignApi } from '@/api'

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

const targetMode = ref('dept')

const templates = [
  { id: 1, subject: '财务报销通知', scene: '系统类', color: '#378ADD', icon: 'mail' },
  { id: 2, subject: 'OA密码重置', scene: '系统类', color: '#1D9E75', icon: 'oa' },
  { id: 3, subject: '中秋福利领取', scene: '节假日', color: '#EF9F27', icon: 'gift' },
  { id: 4, subject: 'HR入职材料提交', scene: 'HR类', color: '#7F77DD', icon: 'user' },
]
const tplForm = reactive({
  template_id: 1 as number,
  sender_name: '财务部-报销系统通知',
  spoof_domain: 'finance-company-notice.com',
})

const landingPages = [
  { id: 1, name: '邮箱登录页', tag: '已适配品牌', label: '企业邮箱登录页', bg: 'linear-gradient(135deg,#378ADD22,#1D9E7522)' },
  { id: 2, name: 'OA登录页', tag: '已适配品牌', label: 'OA系统', bg: 'linear-gradient(135deg,#EF9F2722,#D85A3022)' },
  { id: 3, name: '企业网盘认证', tag: '通用版', label: '网盘认证', bg: 'linear-gradient(135deg,#7F77DD22,#378ADD22)' },
]
const fieldOptions = ref([
  { val: 'account', label: '收集用户名/邮箱', checked: true },
  { val: 'password', label: '收集登录密码（不存储明文）', checked: true },
  { val: 'sms_code', label: '收集手机验证码输入行为', checked: false },
  { val: 'attach', label: '触发附件下载（可选载荷）', checked: false },
])
const landingForm = reactive({ page_id: 1 })

const sendForm = reactive({ profile: 'default' as 'default' | 'custom', test_email: '' })
const testResult = ref('')

const triggerForm = reactive({
  mode: 'schedule' as 'schedule' | 'now',
  schedule_time: '2026-08-20 09:30',
  batch: '3-30',
  adv: [true, true, false],
})

const trainForm = reactive({
  mode: 'train' as 'train' | 'popup' | 'none',
  course_id: '1',
  rule: [true, true, false],
})

const summaryRows = computed(() => [
  { key: '演练名称', val: form.name },
  { key: '演练类型', val: types.find(t => t.value === form.type)?.label || '邮件钓鱼' },
  { key: '目标人数', val: '3,580 人' },
  { key: '邮件模板', val: templates.find(t => t.id === tplForm.template_id)?.subject || '-' },
  { key: '落地页', val: landingPages.find(p => p.id === landingForm.page_id)?.name || '-' },
  { key: '发送配置', val: sendForm.profile === 'default' ? '内置SMTP · SPF/DKIM/DMARC ✓' : '企业自建SMTP' },
  { key: '发送时间', val: triggerForm.mode === 'schedule' ? `${triggerForm.schedule_time}（分3批）` : '立即发送' },
  { key: '培训设置', val: `立即跳转《钓鱼识别与防范》` },
])

async function submit() {
  try {
    await campaignApi.create({
      ...form, auth_confirmed: true,
    })
    ElMessage.success('演练创建成功，已进入调度队列')
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
