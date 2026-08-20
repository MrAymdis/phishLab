/** 平台品牌信息（系统设置-基础参数）：登录页/侧边栏/浏览器标题共享，模块级缓存。 */
import { ref } from 'vue'
import { systemApi } from '@/api'

export interface BrandInfo {
  name: string
  logo: string
  copyright: string
  icp: string
}

const brand = ref<BrandInfo>({ name: '钓鱼演练平台', logo: '', copyright: '', icp: '' })
/** Logo 版本号：上传替换后自增，渲染时拼 ?v= 规避浏览器缓存旧图 */
const logoVersion = ref(0)
let loaded = false
let loading: Promise<void> | null = null

export function useBrand() {
  function loadBrand(): Promise<void> {
    if (loaded) return Promise.resolve()
    if (loading) return loading
    loading = (async () => {
      try {
        // 公开端点：未登录（登录页）也能加载品牌
        const s = (await systemApi.publicSettings()) as Record<string, any>
        if (s && typeof s === 'object') {
          if (s.name) brand.value.name = s.name
          if (s.logo) brand.value.logo = s.logo
          if (s.copyright) brand.value.copyright = s.copyright
          if (s.icp) brand.value.icp = s.icp
        }
      } catch {
        /* 拉取失败保持默认，不影响页面 */
      }
      loaded = true
    })()
    return loading
  }
  /** 本地立即更新（如设置页上传 Logo 后同步到侧边栏/登录页） */
  function updateBrand(patch: Partial<BrandInfo>) {
    if (patch.logo !== undefined && patch.logo !== brand.value.logo) logoVersion.value += 1
    Object.assign(brand.value, patch)
  }
  /** Logo 渲染地址（带版本号防缓存） */
  function logoSrc(): string {
    return brand.value.logo ? `${brand.value.logo}?v=${logoVersion.value}` : ''
  }
  return { brand, logoVersion, loadBrand, updateBrand, logoSrc }
}
