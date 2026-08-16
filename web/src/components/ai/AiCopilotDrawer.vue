<template>
  <el-drawer
    v-model="copilot.visible"
    title="AI Copilot 智能助手"
    direction="rtl"
    size="420px"
  >
    <template #header>
      <div class="drawer-header">
        <span>AI Copilot 智能助手</span>
        <el-tag v-if="contextLabel" size="small" type="info">
          当前上下文：{{ contextLabel }}
        </el-tag>
      </div>
    </template>

    <div ref="listEl" class="chat-list">
      <div
        v-for="(m, i) in copilot.messages"
        :key="i"
        class="chat-item"
        :class="m.role"
      >
        <div class="bubble">
          <div v-if="m.loading && !m.content" class="typing">
            <span /><span /><span />
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-else class="md" v-html="render(m.content)" />
          <div v-if="m.error" class="retry">
            <el-button size="small" link type="primary">重试</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-footer">
      <div class="quick-tags">
        <el-tag
          v-for="q in quickQuestions"
          :key="q"
          class="quick-tag"
          effect="plain"
          @click="copilot.send(q)"
        >
          {{ q }}
        </el-tag>
      </div>
      <div class="input-row">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          placeholder="输入问题，Enter 发送（Shift+Enter 换行）"
          @keydown.enter.exact.prevent="submit"
        />
        <el-button
          type="primary"
          :loading="copilot.streaming"
          :disabled="!input.trim()"
          @click="submit"
        >
          发送
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRoute } from 'vue-router'
import { useCopilotStore } from '@/stores/copilot'

const copilot = useCopilotStore()
const route = useRoute()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const input = ref('')
const listEl = ref<HTMLDivElement>()

const quickQuestions = ['分析演练效果', '生成钓鱼模板', '风险评估建议', '培训推荐']

const contextLabel = computed(() => String(route.meta.title || ''))

function render(text: string) {
  return md.render(text || '')
}

function submit() {
  const text = input.value.trim()
  if (!text) return
  input.value = ''
  copilot.send(text)
}

watch(
  () => copilot.messages.length,
  () => nextTick(() => listEl.value?.scrollTo({ top: listEl.value.scrollHeight })),
)
watch(
  () => copilot.messages.at(-1)?.content,
  () => nextTick(() => listEl.value?.scrollTo({ top: listEl.value.scrollHeight })),
)
</script>

<style scoped lang="scss">
.drawer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
}
.chat-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 8px;
}
.chat-item {
  display: flex;
  &.user {
    justify-content: flex-end;
    .bubble {
      background: var(--color-background-info);
      border-color: var(--color-border-info);
    }
  }
}
.bubble {
  max-width: 85%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.6;
  background: var(--color-background-primary);
}
.md :deep(p) {
  margin: 4px 0;
}
.md :deep(pre) {
  background: var(--color-background-secondary);
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
}
.typing {
  display: inline-flex;
  gap: 4px;
  span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-text-tertiary);
    animation: pulse 1.2s infinite;
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}
.chat-footer {
  border-top: 1px solid var(--color-border-tertiary);
  padding-top: 10px;
}
.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.quick-tag {
  cursor: pointer;
}
.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
</style>
