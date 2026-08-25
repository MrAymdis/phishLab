<template>
  <div class="page-header">
    <div class="page-header-left">
      <el-breadcrumb v-if="parents && parents.length" separator="/">
        <el-breadcrumb-item v-for="p in parents" :key="p">{{ p }}</el-breadcrumb-item>
        <el-breadcrumb-item>{{ title }}</el-breadcrumb-item>
      </el-breadcrumb>
      <h2 v-else class="page-title">{{ title }}</h2>
    </div>
    <div class="page-header-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; parents?: string[] }>()
</script>

<style scoped lang="scss">
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
}
.page-title {
  margin: 0;
  font-size: 16px;
}
.page-header-actions {
  display: flex;
  gap: 8px;
}
</style>
