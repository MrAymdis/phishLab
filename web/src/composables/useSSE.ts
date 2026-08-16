/** SSE 客户端：POST + fetch ReadableStream（EventSource 不支持 POST）。
 * 帧协议：data: {"type":"token|action|done|error", ...}
 */
import { getToken } from '@/api/http'
import type { SseFrame } from '@/types'

export interface SseOptions {
  url: string
  body?: unknown
  onFrame: (frame: SseFrame) => void
  onError?: (err: Error) => void
  onClose?: () => void
}

/** 返回 abort 函数。 */
export function postSSE(opts: SseOptions): () => void {
  const controller = new AbortController()

  ;(async () => {
    try {
      const res = await fetch(opts.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify(opts.body ?? {}),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) {
        throw new Error(`SSE 连接失败: ${res.status}`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE 事件以空行分隔
        let sep: number
        while ((sep = buffer.indexOf('\n\n')) >= 0) {
          const rawEvent = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)
          for (const line of rawEvent.split('\n')) {
            if (!line.startsWith('data:')) continue
            const json = line.slice(5).trim()
            if (!json) continue
            try {
              opts.onFrame(JSON.parse(json) as SseFrame)
            } catch {
              opts.onFrame({ type: 'token', content: json })
            }
          }
        }
      }
      opts.onClose?.()
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        opts.onError?.(err as Error)
      }
    }
  })()

  return () => controller.abort()
}
