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
      <!-- 提交事件的脱敏详情：账号掩码 + 口令长度（口令不落明文） -->
      <div v-if="submitInfo(ev).length" class="ev-submit-info">
        <span v-for="s in submitInfo(ev)" :key="s" class="ev-submit-item">{{ s }}</span>
      </div>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
export interface TimelineEvent {
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

defineProps<{ events: TimelineEvent[] }>()

/** 提交事件的脱敏字段展示：账号 t***e / 密码已输入(10位) */
function submitInfo(ev: TimelineEvent): string[] {
  const detail = ev.detail
  if (!detail || !ev.danger) return []
  const parts: string[] = []
  for (const [key, value] of Object.entries(detail)) {
    if (key === 'fp_hash') continue
    if (key.endsWith('_mask')) {
      const label = key.replace('_mask', '')
      const cn = label.toLowerCase().includes('user') || label.toLowerCase().includes('name')
        ? '账号'
        : label.toLowerCase().includes('phone') || label.toLowerCase().includes('mobile')
          ? '手机号'
          : label
      if (value) parts.push(`${cn} ${value}`)
    } else if (typeof value === 'object' && value !== null && 'len' in (value as Record<string, unknown>)) {
      const label = key.toLowerCase().includes('pass') ? '密码' : key
      const len = (value as { len: number }).len
      parts.push(`${label}已输入（${len} 位）`)
    }
  }
  return parts
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
.ev-submit-info {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}
.ev-submit-item {
  font-size: 12px;
  color: #a32d2d;
  background: rgba(163, 45, 45, 0.08);
  border: 1px solid rgba(163, 45, 45, 0.25);
  border-radius: 4px;
  padding: 2px 8px;
}
</style>
