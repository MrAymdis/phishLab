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
        <span v-if="ev.fingerprint">指纹 {{ ev.fingerprint }}</span>
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
}

defineProps<{ events: TimelineEvent[] }>()
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
}
</style>
