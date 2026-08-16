/** 菜单与路由权限。
 * TODO(一期)：登录后 GET /api/v1/auth/menus 拉取（RBAC ∩ License 模块开关），替换静态表。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

export interface MenuItem {
  path: string
  title: string
  icon: string
}

// 与需求文档一致的 11 项统一导航
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
    // TODO: authApi.menus() 返回后与 License 功能开关求交
  }

  return { menus, loadMenus }
})
