/** AI Copilot 全局会话状态（抽屉组件消费）。 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { postSSE } from '@/composables/useSSE'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  error?: boolean
}

export const useCopilotStore = defineStore('copilot', () => {
  const visible = ref(false)
  const sessionId = ref<number | null>(null)
  const messages = ref<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        '我是您的安全演练 AI 助手，可以帮您分析演练数据、生成模板、撰写报告等。\n\n*AI 生成内容处于草稿态，需人工确认后生效。审核记录将进入审计日志。*',
    },
  ])
  const streaming = ref(false)
  /** 当前页面上下文快照，随请求携带 */
  const pageContext = ref<Record<string, unknown>>({})

  let abort: (() => void) | null = null

  function open(context?: Record<string, unknown>) {
    if (context) pageContext.value = context
    visible.value = true
  }
  function close() {
    visible.value = false
  }

  function send(text: string) {
    if (!text.trim() || streaming.value) return
    messages.value.push({ role: 'user', content: text })
    const answer: ChatMessage = { role: 'assistant', content: '', loading: true }
    messages.value.push(answer)
    streaming.value = true

    abort = postSSE({
      url: '/api/v1/ai/chat/stream',
      body: { session_id: sessionId.value, message: text, page_context: pageContext.value },
      onFrame: (frame) => {
        if (frame.type === 'token' && frame.content) {
          answer.content += frame.content
          answer.loading = false
        } else if (frame.type === 'error') {
          answer.error = true
          answer.loading = false
          answer.content += `\n\n> ${frame.message || '生成失败，请重试'}`
        }
      },
      onError: (err) => {
        answer.error = true
        answer.loading = false
        answer.content = `生成失败：${err.message}`
        streaming.value = false
      },
      onClose: () => {
        answer.loading = false
        streaming.value = false
      },
    })
  }

  function stop() {
    abort?.()
    streaming.value = false
  }

  return { visible, sessionId, messages, streaming, pageContext, open, close, send, stop }
})
