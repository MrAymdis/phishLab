/** 轮询降级：SSE 不可用时的监控大屏刷新。 */
import { onUnmounted, ref } from 'vue'

export function usePolling(fn: () => Promise<void> | void, intervalMs = 5000) {
  const active = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  async function tick() {
    try {
      await fn()
    } catch {
      /* 轮询失败静默，下一轮重试 */
    }
  }

  function start() {
    if (active.value) return
    active.value = true
    void tick()
    timer = setInterval(tick, intervalMs)
  }
  function stop() {
    active.value = false
    if (timer) clearInterval(timer)
    timer = null
  }

  onUnmounted(stop)
  return { active, start, stop }
}
