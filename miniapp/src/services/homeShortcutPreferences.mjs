export const HOME_SHORTCUT_KEY = 'mini.student.home.shortcuts.v1'
export const MAX_HOME_SHORTCUTS = 8

// Store only compact identities, never user-supplied labels, permissions or executable routes.
export function shortcutKey(item) {
  return String(item?.action?.target?.path || '').replace(/^\/pages\//, '')
}

export function decodeShortcuts(value) {
  if (value === undefined || value === 'null') return null
  let parsed
  try { parsed = JSON.parse(value) } catch { throw new Error('常用服务配置异常，请重新编辑后保存') }
  if (!Array.isArray(parsed) || parsed.length > MAX_HOME_SHORTCUTS || parsed.some(key => typeof key !== 'string') || new Set(parsed).size !== parsed.length) throw new Error('常用服务配置异常，请重新编辑后保存')
  return parsed
}

export function encodeShortcuts(keys) {
  const value = JSON.stringify(keys)
  decodeShortcuts(value)
  if (value.length > 500) throw new Error('选择的服务过多，请减少后再保存')
  return value
}

export function resolveShortcuts(keys, directory, defaults) {
  if (keys === null) keys = defaults.map(shortcutKey).slice(0, MAX_HOME_SHORTCUTS)
  const byKey = new Map(directory.map(item => [shortcutKey(item), item]))
  return keys.map(key => byKey.get(key)).filter(Boolean).map(item => ({ key: shortcutKey(item), label: item.name, action: item.action }))
}
