/** Axios 封装：统一响应 {code,message,data}；40101 → 跳登录。 */
import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResult } from '@/types'

const TOKEN_KEY = 'phishlab_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function goLogin(): void {
  clearToken()
  if (location.pathname !== '/login') {
    location.href = `/login?redirect=${encodeURIComponent(location.pathname)}`
  }
}

const http = axios.create({
  baseURL: '', // 路径已含 /api 前缀，dev 由 vite proxy 转发
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => {
    if (response.config.responseType === 'blob') return response // 文件流：跳过统一包装，保留 headers
    const body = response.data as ApiResult
    if (body && typeof body.code === 'number') {
      if (body.code === 0) return body as never
      if (body.code === 40101 || body.code === 40102) {
        goLogin()
        return Promise.reject(new Error(body.message))
      }
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message))
    }
    return response.data
  },
  (error: AxiosError<ApiResult>) => {
    const status = error.response?.status
    const body = error.response?.data
    if (status === 401 || body?.code === 40101) {
      goLogin()
    } else {
      ElMessage.error(body?.message || error.message || '网络错误')
    }
    return Promise.reject(error)
  },
)

/** 便捷方法：直接返回 data 字段 */
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = (await http.get(url, { params })) as unknown as ApiResult<T>
  return res.data
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = (await http.post(url, data)) as unknown as ApiResult<T>
  return res.data
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const res = (await http.put(url, data)) as unknown as ApiResult<T>
  return res.data
}

export async function del<T>(url: string): Promise<T> {
  const res = (await http.delete(url)) as unknown as ApiResult<T>
  return res.data
}

/** 文件下载：POST + blob，解析 Content-Disposition 文件名触发浏览器下载。 */
export async function download(url: string, data?: unknown): Promise<void> {
  const res = await http.post(url, data, { responseType: 'blob' })
  const blob = res.data as Blob
  // 后端错误响应是 JSON 但被按 blob 接收，兜底解析提示
  if (blob.type.includes('json')) {
    const err = (await blob.text()) as string
    try {
      const body = JSON.parse(err) as ApiResult
      ElMessage.error(body.message || '导出失败')
    } catch {
      ElMessage.error('导出失败')
    }
    throw new Error('export failed')
  }
  const disp = (res.headers['content-disposition'] as string) || ''
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(disp)
  const name = m ? decodeURIComponent(m[1]) : `export_${Date.now()}.bin`
  const urlObj = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = urlObj
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(urlObj)
}
