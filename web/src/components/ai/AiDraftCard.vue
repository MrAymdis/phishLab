<template>
  <el-card class="draft-card" shadow="never">
    <div class="draft-head">
      <span class="draft-title">{{ draft.title }}</span>
      <el-tag v-if="draft.status === 'draft'" type="warning" size="small">待审核</el-tag>
      <el-tag v-else-if="draft.status === 'approved'" type="success" size="small">
        已确认 · {{ draft.reviewer }} · {{ draft.reviewed_at }}
      </el-tag>
    </div>
    <div class="draft-preview">{{ draft.content?.slice(0, 160) }}…</div>
    <div v-if="draft.status === 'draft'" class="draft-actions">
      <el-button size="small" @click="$emit('preview', draft)">预览</el-button>
      <el-button size="small" type="primary" @click="$emit('approve', draft)">确认入库</el-button>
      <el-button size="small" type="danger" plain @click="$emit('discard', draft)">丢弃</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
/** AI 生成内容统一审核组件：AI生成 → 预览 → 修改 → 确认入库（全局硬约束）。 */
export interface AiDraft {
  id: number
  biz_type: string
  title?: string
  content?: string
  status: 'draft' | 'approved' | 'discarded'
  reviewer?: string
  reviewed_at?: string
}

defineProps<{ draft: AiDraft }>()
defineEmits<{
  preview: [draft: AiDraft]
  approve: [draft: AiDraft]
  discard: [draft: AiDraft]
}>()
</script>

<style scoped>
.draft-card {
  margin-bottom: 12px;
}
.draft-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.draft-title {
  font-weight: 500;
}
.draft-preview {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 10px;
  line-height: 1.6;
}
.draft-actions {
  display: flex;
  gap: 8px;
}
</style>
