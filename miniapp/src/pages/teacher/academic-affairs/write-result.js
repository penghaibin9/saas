const EXPLICIT_HTTP_REJECTIONS = new Set([400, 401, 403, 404, 409, 410, 412, 422, 429])
const EXPLICIT_BUSINESS_CODES = new Set([
  '400001', '401001', '403001', '403002', '404001', '409001', '410001', '412001', '422001', '429001',
  'DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT', 'LOCKED'
])

export const TEACHER_WRITE_STORAGE_KEY = 'teacher_mp_pending_writes_v1'

function numericServerFailure(value) {
  const number = Number(value)
  return Number.isFinite(number) && ((number >= 500 && number < 600) || (number >= 500000 && number < 600000))
}

// A parsed business envelope only proves that the server answered. A 5xx,
// malformed response or transport failure can have committed the command and
// therefore remains unresolved even if another field looks like a 4xx.
export function isExplicitWriteRejection(error) {
  if (!error) return false
  const code = String(error.code == null ? '' : error.code).toUpperCase()
  const bizCode = String(error.bizCode == null ? '' : error.bizCode).toUpperCase()
  const status = Number(error.httpStatus || error.statusCode || error.status || (error.response && error.response.status))
  if (numericServerFailure(status) || numericServerFailure(code) || numericServerFailure(bizCode)) return false
  if (code === 'BAD_RESPONSE' || code === 'NETWORK' || code === 'TIMEOUT') return false
  if (EXPLICIT_BUSINESS_CODES.has(code) || EXPLICIT_BUSINESS_CODES.has(bizCode)) return true
  return EXPLICIT_HTTP_REJECTIONS.has(status)
}

export function isForbiddenResponse(error) {
  if (!error) return false
  const values = [error.httpStatus, error.statusCode, error.status, error.code, error.bizCode]
  return values.some((value) => String(value == null ? '' : value).startsWith('403'))
}

export function teacherWriteContext(session = {}) {
  const identity = session.identity || {}
  const realUser = session.realUser || {}
  const realRole = realUser.currentRole || {}
  return JSON.stringify([
    String(identity.tenantId || realUser.tenantId || ''),
    String(identity.userId || realUser.userId || (realUser.user && (realUser.user.userId || realUser.user.id)) || ''),
    String(session.currentRole || identity.role || realRole.code || realRole.key || ''),
    String(identity.activeContextId || realUser.activeContextId || realRole.contextId || '')
  ])
}

function recordKey(context, action, objectId) {
  return JSON.stringify([String(context || ''), String(action || ''), String(objectId || '')])
}

function validContext(context) {
  try {
    const parts = JSON.parse(String(context || ''))
    return Array.isArray(parts) && parts.length === 4 && parts.every((part) => String(part || '').trim())
  } catch (_) {
    return false
  }
}

function readRecords() {
  try {
    const raw = uni.getStorageSync(TEACHER_WRITE_STORAGE_KEY)
    if (!raw) return { ok: true, records: {} }
    const records = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!records || Array.isArray(records) || typeof records !== 'object') return { ok: false, records: {} }
    return { ok: true, records }
  } catch (_) {
    return { ok: false, records: {} }
  }
}

function saveRecords(records) {
  try {
    uni.setStorageSync(TEACHER_WRITE_STORAGE_KEY, JSON.stringify(records))
    const checked = readRecords()
    return checked.ok && JSON.stringify(checked.records) === JSON.stringify(records)
  } catch (_) {
    return false
  }
}

export function listPersistentWrites(context) {
  if (!validContext(context)) return { ok: false, records: [] }
  const read = readRecords()
  if (!read.ok) return { ok: false, records: [] }
  return {
    ok: true,
    records: Object.values(read.records).filter((record) => record && record.context === String(context || ''))
  }
}

export function getPersistentWrite(context, action, objectId) {
  if (!validContext(context)) return { ok: false, record: null }
  const read = readRecords()
  if (!read.ok) return { ok: false, record: null }
  return { ok: true, record: read.records[recordKey(context, action, objectId)] || null }
}

// Reserve before POST. If storage cannot be read, written and read back, callers
// must not send the request.
export function beginPersistentWrite(context, action, objectId, meta = {}) {
  if (!validContext(context) || !String(action || '') || !String(objectId || '')) return { ok: false, storageError: true, record: null }
  const requestKey = meta.requestKey == null ? '' : String(meta.requestKey)
  if (requestKey && !/^[A-Za-z0-9_-]{8,128}$/.test(requestKey)) return { ok: false, storageError: true, record: null }
  const read = readRecords()
  if (!read.ok) return { ok: false, storageError: true, record: null }
  const key = recordKey(context, action, objectId)
  if (read.records[key]) return { ok: false, duplicate: true, record: read.records[key] }
  const record = {
    v: 1,
    context: String(context || ''),
    action: String(action || ''),
    objectId: String(objectId || ''),
    state: 'PENDING'
  }
  if (requestKey) record.requestKey = requestKey
  const next = { ...read.records, [key]: record }
  if (!saveRecords(next)) return { ok: false, storageError: true, record: null }
  return { ok: true, record }
}

// Persist the original command acknowledgement before checking whether its page
// or identity is still current. Only server identifiers are retained.
export function persistWriteAck(context, action, objectId, ack = {}) {
  if (!validContext(context)) return false
  const read = readRecords()
  if (!read.ok) return false
  const key = recordKey(context, action, objectId)
  const current = read.records[key]
  if (!current) return false
  const record = { ...current, state: 'ACK' }
  if (ack.ackId != null && String(ack.ackId)) record.ackId = String(ack.ackId)
  if (ack.parentId != null && String(ack.parentId)) record.parentId = String(ack.parentId)
  return saveRecords({ ...read.records, [key]: record })
}

export function clearPersistentWrite(context, action, objectId) {
  if (!validContext(context)) return false
  const read = readRecords()
  if (!read.ok) return false
  const key = recordKey(context, action, objectId)
  if (!read.records[key]) return true
  const next = { ...read.records }
  delete next[key]
  return saveRecords(next)
}
