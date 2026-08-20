import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api'
import { clearToken, getToken, setToken } from '@/api/http'

export const useUserStore = defineStore('user', () => {
  const token = ref(getToken())
  const realName = ref(localStorage.getItem('phishlab_name') || '')

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const data = await authApi.login(username, password)
    token.value = data.token
    realName.value = data.real_name
    setToken(data.token)
    localStorage.setItem('phishlab_name', data.real_name)
  }

  function setRealName(name: string) {
    realName.value = name
    localStorage.setItem('phishlab_name', name)
  }

  function logout() {
    token.value = ''
    realName.value = ''
    clearToken()
    localStorage.removeItem('phishlab_name')
  }

  return { token, realName, isLoggedIn, login, setRealName, logout }
})
