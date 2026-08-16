<template>
  <div class="stat-card card" :class="`card-${accent}`">
    <div class="stat-title">
      <slot name="title">{{ title }}</slot>
    </div>
    <div class="stat-value" :style="{ color: valueColor }">
      {{ value }}<span class="stat-suffix">{{ suffix }}</span>
    </div>
    <div v-if="sub" class="stat-sub">{{ sub }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  value: string | number
  suffix?: string
  sub?: string
  accent?: 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
  valueColor?: string
}>()
</script>

<style scoped lang="scss">
.stat-card {
  min-width: 0;
}
.stat-title {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 26px;
  font-weight: 600;
  line-height: 1.2;
}
.stat-suffix {
  font-size: 13px;
  font-weight: 400;
  margin-left: 2px;
  color: var(--color-text-tertiary);
}
.stat-sub {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 6px;
}
</style>
