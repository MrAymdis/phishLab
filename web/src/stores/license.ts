/** License 授权状态：配额进度 + 功能模块开关（控制菜单/模块可用性）。 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { systemApi } from '@/api'

export const useLicenseStore = defineStore('license', () => {
  const edition = ref<'trial' | 'standard' | 'flagship'>('trial')
  const expireAt = ref('')
  const features = ref<Record<string, boolean>>({
    ai: true,
    openapi: false,
    payload: false,
  })

  async function load() {
    try {
      const data = (await systemApi.license()) as Record<string, unknown>
      if (data?.edition) edition.value = data.edition as never
      if (data?.expire_at) expireAt.value = String(data.expire_at)
      if (data?.features) features.value = data.features as never
    } catch {
      /* 后端未实现时保持默认 */
    }
  }

  function enabled(feature: string): boolean {
    return features.value[feature] !== false
  }

  return { edition, expireAt, features, load, enabled }
})
