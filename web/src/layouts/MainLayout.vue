<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">
        <el-icon :size="20" color="#378ADD"><Aim /></el-icon>
        <span>钓鱼演练平台</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        class="nav-menu"
        :icon-size="15"
      >
        <el-menu-item v-for="m in permission.menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">{{ route.meta.title }}</div>
        <div class="header-right">
          <el-popover placement="bottom-end" :width="300" trigger="click">
            <template #reference>
              <el-badge :value="notifications.length" :max="99" class="notify-badge">
                <el-icon :size="18"><Bell /></el-icon>
              </el-badge>
            </template>
            <div class="notify-panel">
              <div class="notify-title">通知中心</div>
              <div v-for="n in notifications" :key="n.id" class="notify-item">
                <div class="notify-item-title">
                  <el-tag size="small" :type="n.type" effect="plain">{{ n.tag }}</el-tag>
                  {{ n.title }}
                </div>
                <div class="notify-item-time">{{ n.time }}</div>
              </div>
              <div class="notify-footer">查看全部通知</div>
            </div>
          </el-popover>
          <el-dropdown @command="onCommand">
            <span class="user-chip">
              <el-avatar :size="24">{{ (user.realName || 'U').slice(0, 1) }}</el-avatar>
              {{ user.realName || '管理员' }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <!-- Copilot 悬浮球 -->
    <div class="copilot-fab" title="AI Copilot" @click="copilot.open({ route: route.path })">
      <el-icon :size="22"><ChatDotRound /></el-icon>
    </div>

    <AiCopilotDrawer />
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, ChatDotRound } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { useCopilotStore } from '@/stores/copilot'
import AiCopilotDrawer from '@/components/ai/AiCopilotDrawer.vue'

const route = useRoute()
const router = useRouter()
const user = useUserStore()
const permission = usePermissionStore()
const copilot = useCopilotStore()

/** 顶栏通知（mock，后续接 websocket/轮询） */
const notifications = ref([
  { id: 1, tag: '中招预警', type: 'danger' as const, title: 'Q3演练新增 3 名高危中招人员', time: '5 分钟前' },
  { id: 2, tag: '举报', type: 'warning' as const, title: '收到 1 封真实钓鱼举报，待研判处置', time: '32 分钟前' },
  { id: 3, tag: '系统', type: 'info' as const, title: 'SMTP 通道「备用服务器」连通性异常', time: '2 小时前' },
])

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    user.logout()
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
.layout {
  height: 100%;
}
.aside {
  background: var(--color-background-primary);
  border-right: 1px solid var(--color-border-tertiary);
  display: flex;
  flex-direction: column;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  font-weight: 600;
  font-size: 15px;
  border-bottom: 1px solid var(--color-border-tertiary);
}
.nav-menu {
  border-right: none;
  flex: 1;
  --el-menu-item-height: 40px;
  --el-menu-item-font-size: 13px;
}
.header {
  background: var(--color-background-primary);
  border-bottom: 1px solid var(--color-border-tertiary);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-title {
  font-size: 15px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.main {
  padding: 0;
  overflow-y: auto;
}
.notify-badge {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  margin-right: 6px;
}
.notify-panel {
  .notify-title {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
  }
  .notify-item {
    padding: 8px 0;
    border-bottom: 1px dashed var(--color-border-tertiary);
  }
  .notify-item-title {
    font-size: 12px;
    line-height: 1.5;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .notify-item-time {
    font-size: 11px;
    color: var(--color-text-tertiary);
    margin-top: 2px;
  }
  .notify-footer {
    text-align: center;
    font-size: 12px;
    color: var(--color-text-info);
    cursor: pointer;
    padding-top: 8px;
  }
}
.copilot-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-blue), #1E5FA8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(55, 138, 221, 0.45);
  z-index: 100;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  &:hover {
    transform: translateY(-2px) scale(1.05);
    box-shadow: 0 8px 26px rgba(55, 138, 221, 0.6);
  }
}
</style>
