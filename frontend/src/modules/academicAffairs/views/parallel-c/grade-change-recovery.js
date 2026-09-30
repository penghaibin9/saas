const STORAGE_KEY = 'aa-grade-change-recovery-v1'
const OPERATIONS = new Set(['APPLY', 'REVIEW'])
const ACTIONS = new Set(['APPLY', 'APPROVE', 'REJECT'])

function store() {
  if (typeof window === 'undefined' || !window.sessionStorage) throw new Error('当前环境不支持刷新恢复')
  return window.sessionStorage
}

function id(value, required = false) {
  if (value == null || value === '') {
    if (required) throw new Error('恢复引用缺少必要编号')
    return null
  }
  const result = String(value)
  if (!/^[1-9]\d*$/.test(result)) throw new Error('恢复引用编号无效')
  return result
}

function version(value, required = false) {
  if (value == null || value === '') {
    if (required) throw new Error('恢复引用缺少必要版本')
    return null
  }
  const result = Number(value)
  if (!Number.isSafeInteger(result) || result < 0) throw new Error('恢复引用版本无效')
  return result
}

function normalize(entry) {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) throw new Error('恢复引用格式无效')
  const identityRef = typeof entry.identityRef === 'string' && entry.identityRef.length <= 1000 ? entry.identityRef : ''
  const commandKey = typeof entry.commandKey === 'string' && /^[0-9a-f-]{36}$/i.test(entry.commandKey) ? entry.commandKey : ''
  const operation = OPERATIONS.has(entry.operation) ? entry.operation : ''
  const action = ACTIONS.has(entry.action) ? entry.action : ''
  if (!identityRef || !commandKey || !operation || !action) throw new Error('恢复引用身份或操作无效')
  if ((operation === 'APPLY') !== (action === 'APPLY')) throw new Error('恢复引用操作不一致')
  const normalized = {
    identityRef,
    commandKey,
    operation,
    action,
    changeRequestId: id(entry.changeRequestId),
    gradeTaskId: id(entry.gradeTaskId, true),
    gradeRecordId: id(entry.gradeRecordId, true),
    currentTaskId: id(entry.currentTaskId),
    expectedCurrentGradeId: id(entry.expectedCurrentGradeId, operation === 'APPLY'),
    expectedGradeVersion: version(entry.expectedGradeVersion, operation === 'APPLY'),
    expectedRequestVersion: version(entry.expectedRequestVersion, operation === 'REVIEW'),
    expectedTaskVersion: version(entry.expectedTaskVersion, operation === 'REVIEW')
  }
  if (operation === 'REVIEW' && (!normalized.changeRequestId || !normalized.currentTaskId)) throw new Error('审核恢复引用缺少申请或任务编号')
  if (operation === 'APPLY' && normalized.expectedGradeVersion < 1) throw new Error('来源成绩版本无效')
  return normalized
}

function readAll() {
  const parsed = JSON.parse(store().getItem(STORAGE_KEY) || '[]')
  if (!Array.isArray(parsed) || parsed.length > 16) throw new Error('恢复记录格式或数量无效')
  return parsed.map(normalize)
}

function writeAll(entries) {
  if (!Array.isArray(entries) || entries.length > 16) throw new Error('恢复记录数量异常')
  store().setItem(STORAGE_KEY, JSON.stringify(entries.map(normalize)))
}

export function gradeChangeIdentityRef(user = {}, ctx = {}) {
  const tenantId = String(user.tenantId || '')
  const userId = String(user.userId || '')
  const roleCode = String(user.currentRoleCode || '')
  const activeContextId = String(user.activeContextId || '')
  if (!tenantId || !userId || !roleCode) return ''
  return JSON.stringify([
    tenantId,
    userId,
    roleCode,
    activeContextId,
    String(ctx.currentRole?.roleId || ctx.currentRole?.roleCode || ''),
    String(ctx.dataScope?.scopeId || ctx.dataScope?.scopeCode || '')
  ])
}

export function findGradeChangeRecovery(identityRef) {
  try {
    const entries = readAll().filter(entry => entry.identityRef === identityRef)
    if (entries.length > 1) throw new Error('当前身份存在多条未决命令，需要人工核对')
    return { ok: true, entry: entries[0] || null }
  } catch (error) {
    return { ok: false, error: error?.message || '恢复记录不可用' }
  }
}

export function createGradeChangeRecovery(entry) {
  try {
    if (!globalThis.crypto?.randomUUID) throw new Error('当前环境不能生成安全命令标识')
    const entries = readAll()
    const existing = entries.find(item => item.identityRef === entry.identityRef)
    if (existing) return { ok: true, entry: existing, existing: true }
    const next = normalize({ ...entry, commandKey: globalThis.crypto.randomUUID() })
    entries.push(next)
    writeAll(entries)
    return { ok: true, entry: next, existing: false }
  } catch (error) {
    return { ok: false, error: error?.message || '无法保存命令恢复引用' }
  }
}

export function updateGradeChangeRecovery(commandKey, identityRef, patch = {}) {
  try {
    const entries = readAll()
    const index = entries.findIndex(entry => entry.commandKey === commandKey && entry.identityRef === identityRef)
    if (index < 0) throw new Error('命令恢复引用不存在')
    const allowed = ['changeRequestId', 'currentTaskId', 'expectedCurrentGradeId', 'expectedGradeVersion', 'expectedRequestVersion', 'expectedTaskVersion']
    const next = { ...entries[index] }
    allowed.forEach(key => { if (Object.prototype.hasOwnProperty.call(patch, key)) next[key] = patch[key] })
    entries.splice(index, 1, normalize(next))
    writeAll(entries)
    return { ok: true, entry: entries[index] }
  } catch (error) {
    return { ok: false, error: error?.message || '无法更新命令恢复引用' }
  }
}

export function removeGradeChangeRecovery(commandKey, identityRef) {
  try {
    const entries = readAll()
    const next = entries.filter(entry => entry.commandKey !== commandKey || entry.identityRef !== identityRef)
    if (next.length === entries.length) throw new Error('命令恢复引用不存在')
    writeAll(next)
    return { ok: true }
  } catch (error) {
    return { ok: false, error: error?.message || '无法清除命令恢复引用' }
  }
}
