<!-- 企微试发弹窗：接收人从员工档案选取（在职且已配置 userid），也可直接输入 userid -->
<template>
  <el-dialog
    :model-value="modelValue"
    title="企业微信试发"
    width="480px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form label-width="88px">
      <el-form-item label="通道">
        <span class="channel-name">{{ channelName || '—' }}</span>
      </el-form-item>
      <el-form-item label="接收人" required>
        <el-select
          v-model="toUserid"
          filterable
          allow-create
          default-first-option
          remote
          :remote-method="searchCandidates"
          :loading="candidatesLoading"
          placeholder="选择员工，或直接输入企业微信 userid"
          style="width: 100%"
        >
          <el-option
            v-for="u in candidates"
            :key="u.id"
            :label="`${u.name}（${u.wecom_userid}）`"
            :value="u.wecom_userid"
          />
        </el-select>
        <p class="form-hint">接收人须为「用户和组」中已填写企业微信 ID 的在职员工</p>
      </el-form-item>
      <el-form-item v-if="templateId" label="消息模板">
        <span class="channel-name">使用演练所选企微模板（编号 #{{ templateId }}）</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="sending" :disabled="!toUserid" @click="send">
        发送测试消息
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { orgApi, channelApi } from '../../api'

interface Candidate {
  id: number
  name: string
  wecom_userid: string
  email: string
  emp_no: string
}

const props = defineProps<{
  modelValue: boolean
  channelId: number
  channelName?: string
  templateId?: number
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'sent'): void
}>()

const toUserid = ref('')
const candidates = ref<Candidate[]>([])
const candidatesLoading = ref(false)
const sending = ref(false)

async function loadCandidates(kw?: string) {
  candidatesLoading.value = true
  try {
    candidates.value = await orgApi.wecomCandidates(kw)
  } catch {
    candidates.value = []
  } finally {
    candidatesLoading.value = false
  }
}

function searchCandidates(kw: string) {
  loadCandidates(kw)
}

// 弹窗打开时重置并预载候选
watch(() => props.modelValue, (open) => {
  if (open) {
    toUserid.value = ''
    loadCandidates()
  }
})

async function send() {
  if (!toUserid.value) {
    ElMessage.warning('请选择接收人')
    return
  }
  sending.value = true
  try {
    const result = await channelApi.testWecom(
      props.channelId, props.templateId ?? undefined, toUserid.value.trim(),
    )
    if (result.ok) {
      ElMessage.success(`试发成功，请在企业微信查看测试消息（接收人：${toUserid.value.trim()}）`)
      emit('update:modelValue', false)
      emit('sent')
    } else {
      ElMessage.error(`试发失败：${result.message}`)
    }
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.channel-name {
  font-size: 13px;
  color: var(--el-text-color-primary);
}
.form-hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
</style>
