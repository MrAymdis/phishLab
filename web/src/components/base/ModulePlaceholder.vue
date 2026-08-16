<template>
  <div class="page-container">
    <PageHeader :title="title" />
    <div class="placeholder card" style="margin: 16px">
      <el-alert
        :title="`当前为脚手架占位页面 —— ${title}模块将在${phase}实现`"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <h4 style="margin: 0 0 8px">规划功能（对照前端 demo）</h4>
      <ul class="feature-list">
        <li v-for="f in features" :key="f">{{ f }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/base/PageHeader.vue'

defineProps<{ title: string; features: string[]; phase?: string }>()
</script>

<style scoped>
.feature-list {
  margin: 0;
  padding-left: 20px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.9;
}
</style>
