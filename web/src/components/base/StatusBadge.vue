<template>
  <el-tag :type="tag.type" size="small" effect="light">
    <span v-if="tag.live" class="live-dot" style="margin-right: 4px" />{{ tag.label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const MAP: Record<string, { label: string; type: 'info' | 'warning' | 'success' | 'danger' | 'primary'; live?: boolean }> = {
  draft: { label: '草稿', type: 'info' },
  scheduled: { label: '待开始', type: 'warning' },
  sending: { label: '发送中', type: 'primary', live: true },
  running: { label: '进行中', type: 'success', live: true },
  paused: { label: '已暂停', type: 'info' },
  completed: { label: '已完成', type: 'success' },
  terminated: { label: '已终止', type: 'danger' },
}

const tag = computed(() => MAP[props.status] ?? { label: props.status, type: 'info' as const })
</script>
