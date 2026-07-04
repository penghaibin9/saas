/**
 * 配置聚合入口 + 品牌主题应用
 */
import { tenantBrandConfig } from './brand.config'
import roleConfigs, { ROLE, getRoleConfig, hasAction, teacherIdentities } from './roles.config'

/**
 * 将 tenantBrandConfig 的品牌色写入 CSS 变量，实现按学校换肤。
 * H5 端直接写 documentElement；小程序端由默认 tokens 兜底（V1 不强依赖动态换肤）。
 */
export function applyBrandTheme(brand = tenantBrandConfig) {
  const c = brand && brand.colors
  if (!c) return
  // #ifdef H5
  try {
    const root = document.documentElement
    if (c.primary) root.style.setProperty('--brand-primary', c.primary)
    if (c.primaryStrong) root.style.setProperty('--brand-primary-strong', c.primaryStrong)
    if (c.primary) root.style.setProperty('--primary-600', c.primary)
    if (c.teacher) root.style.setProperty('--teacher-600', c.teacher)
  } catch (e) {
    // 忽略：非浏览器环境
  }
  // #endif
}

export { tenantBrandConfig, roleConfigs, ROLE, getRoleConfig, hasAction, teacherIdentities }
