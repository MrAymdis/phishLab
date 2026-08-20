<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">
        <img v-if="brand.logo" :src="logoSrc()" class="aside-logo-img" alt="平台 Logo" />
        <el-icon v-else :size="20" color="#378ADD"><Aim /></el-icon>
        <span>{{ brand.name }}</span>
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
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 个人中心：资料 + 修改密码 -->
      <el-dialog v-model="profileDialog" title="个人中心" width="440px">
        <el-tabs v-model="profileTab">
          <el-tab-pane label="基本资料" name="info">
            <el-form label-width="80px">
              <el-form-item label="登录名">
                <el-input :model-value="user.username" disabled />
              </el-form-item>
              <el-form-item label="姓名">
                <el-input v-model="profileForm.real_name" placeholder="真实姓名" />
              </el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="修改密码" name="pwd">
            <el-form label-width="80px">
              <el-form-item label="原密码" required>
                <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="当前登录密码" />
              </el-form-item>
              <el-form-item label="新密码" required>
                <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 8 位" />
              </el-form-item>
              <el-form-item label="确认密码" required>
                <el-input v-model="pwdForm.confirm" type="password" show-password placeholder="再次输入新密码" />
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
        <template #footer>
          <el-button size="small" @click="profileDialog = false">关闭</el-button>
          <el-button size="small" type="primary" :loading="profileSaving"
            @click="saveProfile">{{ profileTab === 'info' ? '保存资料' : '确认修改' }}</el-button>
        </template>
      </el-dialog>

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
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reactive } from 'vue'
import { Bell, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { useCopilotStore } from '@/stores/copilot'
import { useBrand } from '@/composables/useBrand'
import AiCopilotDrawer from '@/components/ai/AiCopilotDrawer.vue'

const route = useRoute()
const router = useRouter()
const user = useUserStore()
const permission = usePermissionStore()
const copilot = useCopilotStore()
const { brand, loadBrand, logoSrc } = useBrand()

onMounted(() => {
  if (user.isLoggedIn) permission.loadMenus()
  void loadBrand()
})

// 浏览器标题跟随平台名称（品牌加载完成后覆盖硬编码后缀）
watch(
  () => [route.meta.title, brand.value.name] as const,
  ([title, name]) => {
    document.title = `${String(title || '')} - ${name}`
  },
  { immediate: true },
)

/** 顶栏通知（mock，后续接 websocket/轮询） */
const notifications = ref([
  { id: 1, tag: '中招预警', type: 'danger' as const, title: 'Q3演练新增 3 名高危中招人员', time: '5 分钟前' },
  { id: 2, tag: '举报', type: 'warning' as const, title: '收到 1 封真实钓鱼举报，待研判处置', time: '32 分钟前' },
  { id: 3, tag: '系统', type: 'info' as const, title: 'SMTP 通道「备用服务器」连通性异常', time: '2 小时前' },
])

// ---- 个人中心 ----
const profileDialog = ref(false)
const profileTab = ref('info')
const profileSaving = ref(false)
const profileForm = reactive({ real_name: '' })
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })

function onCommand(cmd: string) {
  if (cmd === 'profile') {
    profileForm.real_name = user.realName
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm = ''
    profileTab.value = 'info'
    profileDialog.value = true
  } else if (cmd === 'logout') {
    user.logout()
    router.push('/login')
  }
}

async function saveProfile() {
  if (profileTab.value === 'pwd') {
    if (pwdForm.new_password.length < 8) {
      ElMessage.warning('新密码至少 8 位')
      return
    }
    if (pwdForm.new_password !== pwdForm.confirm) {
      ElMessage.warning('两次输入的新密码不一致')
      return
    }
  }
  profileSaving.value = true
  try {
    if (profileTab.value === 'info') {
      await authApi.updateProfile(profileForm.real_name.trim())
      user.setRealName(profileForm.real_name.trim())
      ElMessage.success('资料已保存')
    } else {
      await authApi.changePassword(pwdForm.old_password, pwdForm.new_password)
      ElMessage.success('密码已修改，下次登录生效')
      profileDialog.value = false
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : String(err))
  } finally {
    profileSaving.value = false
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
.aside-logo-img {
  width: 22px;
  height: 22px;
  object-fit: contain;
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
