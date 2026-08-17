<template>
  <div class="funnel-list">
    <div v-for="(item, idx) in items" :key="item.name" class="funnel-item">
      <span class="funnel-label">{{ item.name }}</span>
      <div class="funnel-bar-wrap">
        <div class="funnel-bar" :style="{ width: barWidth(item.value), background: colors[idx % colors.length] }">
          {{ item.value.toLocaleString() }}
        </div>
      </div>
      <span class="funnel-value">{{ item.value.toLocaleString() }} 人</span>
      <span class="funnel-rate">{{ item.rate ?? '' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface FunnelItem {
  name: string
  value: number
  rate?: string
}

const props = withDefaults(defineProps<{ items: FunnelItem[]; height?: string }>(), {
  height: '300px',
})

const colors = ['#378ADD', '#7F77DD', '#D85A30', '#A32D2D', '#1D9E75', '#EF9F27']

// 随 items 变化重算（接口加载后刷新比例）
const max = computed(() => Math.max(...props.items.map((i) => i.value), 1))
function barWidth(val: number): string {
  return Math.max(8, (val / max.value) * 100) + '%'
}
</script>

<style scoped lang="scss">
.funnel-list {
  padding: 4px 0;
}
.funnel-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  &:last-child { margin-bottom: 0; }
}
.funnel-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  width: 70px;
  flex-shrink: 0;
}
.funnel-bar-wrap {
  flex: 1;
  min-width: 0;
}
.funnel-bar {
  height: 28px;
  border-radius: 4px 14px 14px 4px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  color: white;
  font-size: 11px;
  font-weight: 500;
  transition: width 0.6s ease;
  min-width: 36px;
}
.funnel-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  width: 70px;
  text-align: right;
  flex-shrink: 0;
}
.funnel-rate {
  font-size: 11px;
  color: var(--color-text-tertiary);
  width: 60px;
  text-align: right;
  flex-shrink: 0;
}
</style>
