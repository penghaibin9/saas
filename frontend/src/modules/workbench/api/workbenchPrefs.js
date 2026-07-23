/**
 * 工作台个人偏好（P7）——读写 /me/preferences，按角色分键。
 * 偏好只影响展示顺序/显隐，绝不改变权限或数据范围。
 */
import { request } from '@/services/http'

export function tilesPrefKey(role) {
  return `workbench.tiles.${String(role || 'DEFAULT').toUpperCase()}`
}

export function favoritesPrefKey(role) {
  return `workbench.favorites.${String(role || 'DEFAULT').toUpperCase()}`
}

/** 磁贴点击次数（P7 埋点，仅本人偏好，不影响权限） */
export function clicksPrefKey(role) {
  return `workbench.clicks.${String(role || 'DEFAULT').toUpperCase()}`
}

/** @returns {Promise<Record<string,string>>} */
export async function loadPrefs(keys) {
  const d = await request('/me/preferences', { params: { keys: keys.join(',') } })
  return (d && d.items) || {}
}

export async function savePref(key, value) {
  const v = typeof value === 'string' ? value : JSON.stringify(value)
  await request('/me/preferences', { method: 'POST', body: { key, value: v.slice(0, 500) } })
}

export function parseJsonPref(raw, fallback) {
  if (!raw) return fallback
  try {
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

/** 按偏好重排并过滤汇总磁贴；未知 key 忽略，不发明新磁贴。 */
export function applyTilePrefs(cues, pref) {
  const list = Array.isArray(cues) ? [...cues] : []
  const hidden = new Set((pref && pref.hidden) || [])
  const order = Array.isArray(pref && pref.order) ? pref.order : []
  const byKey = new Map(list.map((c) => [c.key, c]))
  const out = []
  for (const k of order) {
    if (byKey.has(k) && !hidden.has(k)) {
      out.push(byKey.get(k))
      byKey.delete(k)
    }
  }
  for (const c of list) {
    if (byKey.has(c.key) && !hidden.has(c.key)) out.push(c)
  }
  return out
}

/** 收藏路径优先；空收藏回落配方默认 quickLinks。 */
export function applyFavoriteLinks(defaultLinks, favPaths) {
  const defaults = Array.isArray(defaultLinks) ? defaultLinks : []
  const favs = Array.isArray(favPaths) ? favPaths.filter(Boolean) : []
  if (!favs.length) return defaults.map((l) => ({ ...l, favorited: true }))
  const byTo = new Map(defaults.map((l) => [l.to, l]))
  const out = []
  for (const to of favs) {
    if (byTo.has(to)) out.push({ ...byTo.get(to), favorited: true })
  }
  for (const l of defaults) {
    if (!favs.includes(l.to)) out.push({ ...l, favorited: false })
  }
  return out
}

/** 递增磁贴点击计数；保留最多 40 个 key，保证 JSON ≤ 500 字符。 */
export function bumpClickCount(clicks, cueKey) {
  const map = clicks && typeof clicks === 'object' ? { ...clicks } : {}
  const k = String(cueKey || '').slice(0, 40)
  if (!k) return map
  map[k] = (Number(map[k]) || 0) + 1
  const keys = Object.keys(map)
  if (keys.length > 40) {
    keys.sort((a, b) => (map[a] || 0) - (map[b] || 0))
    for (const drop of keys.slice(0, keys.length - 40)) delete map[drop]
  }
  return map
}
