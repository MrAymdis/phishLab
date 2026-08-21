import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api'
import { clearToken, getToken, setToken } from '@/api/http'

export const useUserStore = defineStore('user', () => {
  const token = ref(getToken())
  const username = ref(localStorage.getItem('phishlab_username') || '')
  const realName = ref(localStorage.getItem('phishlab_name') || '')

  const isLoggedIn = computed(() => !!token.value)

  async function login(account: string, password: string) {
    const data = await authApi.login(account, password)
    token.value = data.token
    username.value = data.username
    realName.value = data.real_name
    setToken(data.token)
    localStorage.setItem('phishlab_username', data.username)
    localStorage.setItem('phishlab_name', data.real_name)
  }

  function setRealName(name: string) {
    realName.value = name
    localStorage.setItem('phishlab_name', name)
  }

  function logout() {
    token.value = ''
    username.value = ''
    realName.value = ''
    clearToken()
    localStorage.removeItem('phishlab_username')
    localStorage.removeItem('phishlab_name')
  }

  return { token, username, realName, isLoggedIn, login, setRealName, logout }
})
