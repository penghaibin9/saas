export const COMMON_SERVICE_LIMIT = 6

export function commonServiceStorageKey(session) {
  const tenant = session.realUser?.tenantId, user = session.identity?.userId
  if (tenant == null || !user || !session.currentRole || !session.persistedIdentityVerified) return ''
  return 'teacher-common-services:v1:' + [tenant, user, session.currentRole, session.realUser?.activeContextId || '']
    .map(value => encodeURIComponent(String(value))).join(':')
}

export function defaultCommonServiceKeys(services, role) {
  const preferred = role === 'counselor' ? ['affairsLeave', 'myClasses', 'talk'] : []
  return [...services.filter(item => preferred.includes(item.key)).sort((a,b) => preferred.indexOf(a.key) - preferred.indexOf(b.key)),
    ...services.filter(item => !preferred.includes(item.key))].slice(0,3).map(item => item.key)
}

export function allowedCommonServiceKeys(keys, services) {
  const available = new Set(services.filter(item => item.path && !item.disabledReason).map(item => item.key))
  return [...new Set(keys)].filter(key => available.has(key)).slice(0, COMMON_SERVICE_LIMIT)
}

export function readCommonServiceKeys(storage, key) {
  if (!key) throw new Error('工作身份尚未确认，请刷新后再试。')
  const raw = storage.getStorageSync(key)
  if (raw === '' || raw == null) return null
  const value = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (value?.version !== 1 || !Array.isArray(value.keys) || value.keys.some(item => typeof item !== 'string')) {
    throw new Error('常用服务设置无法读取，请重试。')
  }
  return value.keys
}

export function saveCommonServiceKeys(storage, key, keys) {
  if (!key) throw new Error('工作身份尚未确认，请刷新后再试。')
  storage.setStorageSync(key, JSON.stringify({ version: 1, keys }))
  const saved = readCommonServiceKeys(storage, key)
  if (JSON.stringify(saved) !== JSON.stringify(keys)) throw new Error('设置未保存成功，请重试。')
}
