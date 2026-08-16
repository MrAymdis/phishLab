<template>
  <div class="login-page">
    <div class="login-card card card-blue">
      <div class="login-logo">
        <el-icon :size="34" color="#378ADD"><Aim /></el-icon>
        <h1>钓鱼演练平台</h1>
        <p>企业安全意识演练与培训闭环</p>
      </div>
      <el-form :model="form" @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="form.username" size="large" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            placeholder="密码"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          native-type="submit"
        >
          登 录
        </el-button>
      </el-form>
      <div class="login-tip">仅授权安全人员可用 · 演练数据严格保密 · 教育为主，惩罚为辅</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(String(route.query.redirect || '/'))
  } catch {
    /* http 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f6ff 0%, #f5f5f5 100%);
}
.login-card {
  width: 380px;
  padding: 36px 32px;
}
.login-logo {
  text-align: center;
  margin-bottom: 28px;
  h1 {
    margin: 10px 0 4px;
    font-size: 20px;
  }
  p {
    margin: 0;
    color: var(--color-text-tertiary);
    font-size: 12px;
  }
}
.login-tip {
  margin-top: 18px;
  font-size: 11px;
  color: var(--color-text-tertiary);
  text-align: center;
  line-height: 1.6;
}
</style>
