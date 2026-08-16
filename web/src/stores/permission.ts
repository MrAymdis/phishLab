/** 菜单与路由权限：登录后 GET /api/v1/auth/menus 拉取（后端按 License 模块开关过滤）。 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api'

export interface MenuItem {
  path: string
  title: string
  icon: string
}

// 与需求文档一致的 11 项统一导航（接口失败时的兜底）
const DEFAULT_MENUS: MenuItem[] = [
  { path: '/dashboard', title: '数据概览', icon: 'Odometer' },
  { path: '/campaign', title: '演练管理', icon: 'Aim' },
  { path: '/template', title: '素材模板', icon: 'Files' },
  { path: '/send-config', title: '发送配置', icon: 'Message' },
  { path: '/users', title: '用户和组', icon: 'User' },
  { path: '/training', title: '安全培训', icon: 'Reading' },
  { path: '/reports', title: '数据报表', icon: 'DataAnalysis' },
  { path: '/mail-report', title: '邮件举报', icon: 'Bell' },
  { path: '/settings', title: '系统设置', icon: 'Setting' },
  { path: '/ai', title: '智能助手', icon: 'ChatDotRound' },
  { path: '/openapi', title: 'API开放平台', icon: 'Connection' },
]

export const usePermissionStore = defineStore('permission', () => {
  const menus = ref<MenuItem[]>(DEFAULT_MENUS)

  async function loadMenus() {
    try {
      const data = await authApi.menus()
      if (Array.isArray(data) && data.length) {
        menus.value = data
      }
    } catch {
      // 接口失败保留默认菜单
    }
  }

  return { menus, loadMenus }
})
