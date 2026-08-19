<template>
  <el-timeline>
    <el-timeline-item
      v-for="(ev, i) in events"
      :key="i"
      :timestamp="ev.time"
      :type="ev.danger ? 'danger' : ev.good ? 'success' : 'primary'"
    >
      <div class="ev-head">
        <b>{{ ev.user }}</b>
        <span class="ev-action">
          {{ ev.icon }} {{ ev.action }}
          <el-tag v-if="ev.danger" type="danger" size="small" style="margin-left:6px">中招！</el-tag>
          <el-tag v-else-if="ev.good" type="success" size="small" style="margin-left:6px">表现优秀！</el-tag>
        </span>
      </div>
      <div class="ev-meta">
        <span>IP {{ ev.ip }}</span>
        <span>浏览器 {{ ev.browser }}</span>
        <span v-if="ev.fingerprint" class="ev-fp" :title="`完整指纹：${ev.fingerprint}`">指纹 {{ ev.fingerprint }}</span>
      </div>
      <!-- 提交事件的表单详情：字段名 + 值表格（账号掩码/口令首尾原样呈现，密文不落明文） -->
      <table v-if="submitRows(ev).length" class="ev-submit-table">
        <tbody>
          <tr v-for="r in submitRows(ev)" :key="r.label">
            <td class="ev-submit-label">{{ r.label }}</td>
            <td class="ev-submit-value">{{ r.value }}</td>
          </tr>
        </tbody>
        <tfoot v-if="canReveal(ev)">
          <tr>
            <td colspan="2">
              <a class="ev-reveal" @click.prevent="revealFields(ev)">查看全部明文（需取证操作密码）</a>
            </td>
          </tr>
        </tfoot>
      </table>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'

export interface TimelineEvent {
  id?: number
  time: string
  user: string
  action: string
  icon: string
  ip: string
  browser: string
  fingerprint?: string
  danger?: boolean
  good?: boolean
  detail?: Record<string, unknown>
}

const props = defineProps<{ events: TimelineEvent[]; campaignId?: number }>()

/** 事件是否含可取证密文（任一 *_plain 字段） */
function canReveal(ev: TimelineEvent): boolean {
  if (!ev.detail || !ev.danger || !ev.id) return false
  return Object.values(ev.detail).some(
    (v) => typeof v === 'object' && v !== null && (v as Record<string, unknown>).encrypted != null,
  )
}

/** 取证：输入操作密码 → 解密全部明文（AES-GCM），服务端全程审计。 */
async function revealFields(ev: TimelineEvent): Promise<void> {
  try {
    const { value: op } = await ElMessageBox.prompt('请输入取证操作密码（系统设置中配置）', `取证 · ${ev.user}`, {
      inputType: 'password',
      confirmButtonText: '解密',
      cancelButtonText: '取消',
      inputPlaceholder: '取证操作密码',
    })
    if (!op) return
    const { campaignApi } = await import('@/api')
    const res = await campaignApi.revealSubmitPassword(props.campaignId ?? 0, ev.id!, { operation_password: op })
    const rows = res.fields
      .map((f) => ({ label: FIELD_LABELS[f.name.toLowerCase()] ?? f.name, value: f.value }))
      .map((r) => `<tr><td style="padding:4px 12px;color:#a32d2d;background:rgba(163,45,45,.08);white-space:nowrap;font-weight:600;border:1px solid rgba(163,45,45,.25)">${r.label}</td><td style="padding:4px 12px;word-break:break-all;border:1px solid rgba(163,45,45,.25)">${r.value}</td></tr>`)
      .join('')
    ElMessageBox.alert(
      `<table style="border-collapse:collapse;font-size:13px;width:100%">${rows}</table>
       <p style="font-size:12px;color:#999;margin-top:10px">该操作已记录审计日志（${ev.user} 提交事件的完整明文）</p>`,
      `提交的全部明文 · ${ev.user}`,
      {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '我知道了',
      },
    )
  } catch (err) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(`取证失败：${err instanceof Error ? err.message : String(err)}`)
  }
}

/** 提交事件的表单字段表格：字段名 → 中文标签，值原样展示（掩码/口令首尾字符）。
 *  口令不落完整明文（红线）：库中形态为 {len, first, last}，展示首尾字符中间星号填充；
 *  仅存长度（≤2 位或历史数据）时展示"已输入（N 位）"。 */
const FIELD_LABELS: Record<string, string> = {
  uid: '账号',
  username: '账号',
  user: '账号',
  password: '密码',
  pwd: '密码',
  smsaddr: '手机号',
  phone: '手机号',
  mobile: '手机号',
  locale: '语言',
  verifycode: '验证码',
  verifycellcode: '短信验证码',
}
function submitRows(ev: TimelineEvent): { label: string; value: string }[] {
  const detail = ev.detail
  if (!detail || !ev.danger) return []
  const rows: { label: string; value: string }[] = []
  for (const [key, value] of Object.entries(detail)) {
    if (key.endsWith('_mask')) {
      if (!value) continue
      const base = key.replace(/_mask$/, '')
      rows.push({
        label: FIELD_LABELS[base.toLowerCase()] ?? base,
        value: String(value),
      })
    } else if (typeof value === 'object' && value !== null && 'len' in (value as Record<string, unknown>)) {
      const len = (value as { len: number; first?: string; last?: string }).len
      const { first, last } = value as { first?: string; last?: string }
      // 首尾字符 + 中间星号填充；无首尾数据（≤2 位或历史事件）退化为仅长度
      const shown = first && last
        ? `${first}${'*'.repeat(Math.max(0, len - 2))}${last}`
        : `已输入（${len} 位）`
      rows.push({ label: FIELD_LABELS[key.toLowerCase()] ?? key, value: shown })
    } else if (key === 'fp_hash' && value) {
      rows.push({ label: '设备指纹', value: String(value) })
    }
  }
  return rows
}
</script>

<style scoped>
.ev-head {
  font-size: 13px;
  display: flex;
  gap: 8px;
  align-items: center;
}
.ev-meta {
  font-size: 12px;
  color: var(--color-text-tertiary);
  display: flex;
  gap: 14px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.ev-fp {
  font-family: ui-monospace, 'Courier New', monospace;
  word-break: break-all;
}
.ev-submit-table {
  margin-top: 8px;
  border-collapse: collapse;
  font-size: 12px;
  min-width: 260px;
}
.ev-submit-table td {
  border: 1px solid rgba(163, 45, 45, 0.25);
  padding: 4px 10px;
}
.ev-submit-label {
  color: #a32d2d;
  background: rgba(163, 45, 45, 0.08);
  white-space: nowrap;
  font-weight: 600;
}
.ev-submit-value {
  color: #5c0d0d;
  word-break: break-all;
}
</style>
