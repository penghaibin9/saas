/** 依据 portal-config.modules 生成可见菜单：关闭的模块不出现。dashboard 始终可见。 */
import { MODULES } from './moduleRegistry'

export function buildMenu(config) {
  const mods = config?.modules || {}
  const enabled = !!config?.enabled
  return MODULES.filter((m) => m.key === 'dashboard' || (enabled && mods[m.key])).map((m) => ({
    key: m.key,
    title: m.title,
    icon: m.icon,
    to: m.path === 'home' ? '/home' : `/${m.path}`
  }))
}
