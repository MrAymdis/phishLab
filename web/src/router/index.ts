import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { getToken } from '@/api/http'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/dashboard/DashboardView.vue'), meta: { title: '数据概览' } },
      { path: 'campaign', name: 'campaign-list', component: () => import('@/views/campaign/CampaignListView.vue'), meta: { title: '演练管理' } },
      { path: 'campaign/create', name: 'campaign-create', component: () => import('@/views/campaign/CampaignWizard.vue'), meta: { title: '发起演练' } },
      { path: 'campaign/:id', name: 'campaign-detail', component: () => import('@/views/campaign/CampaignDetail.vue'), meta: { title: '演练详情监控' } },
      { path: 'template', name: 'template', component: () => import('@/views/template/TemplateView.vue'), meta: { title: '素材模板' } },
      { path: 'send-config', name: 'send-config', component: () => import('@/views/send-config/SendConfigView.vue'), meta: { title: '发送配置' } },
      { path: 'users', name: 'users', component: () => import('@/views/users/UsersView.vue'), meta: { title: '用户和组' } },
      { path: 'training', name: 'training', component: () => import('@/views/training/TrainingView.vue'), meta: { title: '安全培训' } },
      { path: 'reports', name: 'reports', component: () => import('@/views/reports/ReportsView.vue'), meta: { title: '数据报表' } },
      { path: 'mail-report', name: 'mail-report', component: () => import('@/views/mail-report/MailReportView.vue'), meta: { title: '邮件举报' } },
      { path: 'settings', name: 'settings', component: () => import('@/views/settings/SettingsView.vue'), meta: { title: '系统设置' } },
      { path: 'ai', name: 'ai', component: () => import('@/views/ai/AiView.vue'), meta: { title: '智能助手' } },
      { path: 'openapi', name: 'openapi', component: () => import('@/views/openapi/OpenApiView.vue'), meta: { title: 'API开放平台' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${String(to.meta.title || '')} - 钓鱼演练平台`
  if (!to.meta.public && !getToken()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && getToken()) return { path: '/' }
})

export default router
