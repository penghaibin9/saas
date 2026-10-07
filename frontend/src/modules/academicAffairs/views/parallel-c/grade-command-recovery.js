const STORAGE_KEY = 'aa-grade-command-recovery-v1'
const OPERATIONS = new Set(['RECHECK_REVIEW', 'RECOGNITION_SUBMIT', 'RECOGNITION_REVIEW', 'GRADE_COMPONENT_BATCH_SAVE', 'GRADE_TASK_SUBMIT'])

function store() {
  if (typeof window === 'undefined' || !window.sessionStorage) throw new Error('当前环境不支持刷新恢复')
  return window.sessionStorage
}

function clean(entry) {
  const commandKey = typeof entry?.commandKey === 'string' ? entry.commandKey : ''
  const operation = OPERATIONS.has(entry?.operation) ? entry.operation : ''
  const identityRef = typeof entry?.identityRef === 'string' && entry.identityRef.length <= 500 ? entry.identityRef : ''
  const objectId = entry?.objectId == null || entry.objectId === '' ? null : String(entry.objectId)
  const page = Number(entry?.page)
  const status = typeof entry?.status === 'string' && entry.status.length <= 32 ? entry.status : ''
  const rosterVersionId = entry?.rosterVersionId == null ? null : String(entry.rosterVersionId)
  if (rosterVersionId !== null && !/^[1-9]\d*$/.test(rosterVersionId)) return null
  if (!/^[0-9a-f-]{36}$/i.test(commandKey) || !operation || !identityRef || (objectId != null && !/^[1-9]\d*$/.test(objectId))) return null
  return { commandKey, operation, identityRef, objectId, rosterVersionId, page: Number.isInteger(page) && page > 0 && page <= 100000 ? page : 1, status, createdAt: Number(entry.createdAt) || Date.now(), confirmedAt: Number(entry.confirmedAt) || null }
}

function readAll() {
  const value = JSON.parse(store().getItem(STORAGE_KEY) || '[]')
  if (!Array.isArray(value)) throw new Error('恢复记录格式无效')
  const entries = value.map(clean)
  if (entries.some(entry => !entry)) throw new Error('恢复记录不完整，不能跳过原命令继续提交')
  return entries.sort((a, b) => a.createdAt - b.createdAt)
}

function writeAll(entries) {
  const normalized = entries.map(clean)
  if (normalized.some(entry => !entry)) throw new Error('恢复记录不完整，原引用已保留')
  store().setItem(STORAGE_KEY, JSON.stringify(normalized))
}

export function gradeCommandIdentityRef(user = {}) {
  const tenantId = String(user.tenantId || ''), userId = String(user.userId || ''), role = String(user.currentRoleCode || '')
  if (!tenantId || !userId || !role) return ''
  return JSON.stringify([tenantId, userId, role, String(user.activeContextId || '')])
}

export function findGradeCommandReference(identityRef, operations, objectId) {
  try {
    const allowed = new Set(Array.isArray(operations) ? operations : [operations])
    const entries = readAll().filter(entry => entry.identityRef === identityRef && allowed.has(entry.operation) && (objectId === undefined || entry.objectId === String(objectId)))
    return { ok: true, entry: entries.at(-1) || null }
  } catch (error) { return { ok: false, error: error?.message || '恢复记录不可用' } }
}

export function createGradeCommandReference({ identityRef, operation, objectId = null, page = 1, status = '', rosterVersionId = null }) {
  try {
    if (!globalThis.crypto?.randomUUID) throw new Error('当前环境不能生成安全命令键')
    const entries = readAll(), normalizedObjectId = objectId == null || objectId === '' ? null : String(objectId)
    const duplicate = entries.find(entry => entry.identityRef === identityRef && entry.operation === operation && entry.objectId === normalizedObjectId)
    if (duplicate) return { ok: true, entry: duplicate, existing: true }
    if (entries.length >= 40) throw new Error('待恢复命令较多，请先核对原命令；不会删除旧引用以发送新请求')
    const entry = clean({ commandKey: globalThis.crypto.randomUUID(), identityRef, operation, objectId: normalizedObjectId, rosterVersionId, page, status, createdAt: Date.now() })
    if (!entry) throw new Error('命令恢复引用无效')
    entries.push(entry); writeAll(entries)
    return { ok: true, entry, existing: false }
  } catch (error) { return { ok: false, error: error?.message || '无法保存命令恢复引用' } }
}

export function updateGradeCommandReference(commandKey, identityRef, patch = {}) {
  try {
    const entries = readAll(), index = entries.findIndex(entry => entry.commandKey === commandKey && entry.identityRef === identityRef)
    if (index < 0) throw new Error('命令恢复引用不存在')
    const next = clean({ ...entries[index], objectId: patch.objectId ?? entries[index].objectId, page: patch.page ?? entries[index].page, status: patch.status ?? entries[index].status, confirmedAt: patch.confirmedAt ?? entries[index].confirmedAt })
    if (!next) throw new Error('命令恢复引用更新无效')
    entries.splice(index, 1, next); writeAll(entries)
    return { ok: true, entry: next }
  } catch (error) { return { ok: false, error: error?.message || '无法更新命令恢复引用' } }
}

export function removeGradeCommandReference(commandKey, identityRef) {
  try {
    const entries = readAll(), next = entries.filter(entry => entry.commandKey !== commandKey || entry.identityRef !== identityRef)
    writeAll(next); return { ok: true }
  } catch (error) { return { ok: false, error: error?.message || '无法清除命令恢复引用' } }
}
