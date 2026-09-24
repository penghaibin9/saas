import { teacherWriteContext } from './write-result.js'

export function approvalContextKey(session) { return teacherWriteContext(session) }

function serverFailure(error) {
  return [error?.httpStatus, error?.status, error?.statusCode, error?.response?.status, error?.code, error?.bizCode].some(value => {
    const code = Number(value)
    return (code >= 500 && code < 600) || (code >= 500000 && code < 600000)
  })
}

export function isApprovalForbidden(error) {
  if (serverFailure(error)) return false
  const status = Number(error && (error.status || error.statusCode || error.httpStatus || (error.response && error.response.status)))
  const codes = [error && error.code, error && error.bizCode].map((value) => String(value || '').toUpperCase())
  return status === 403 || codes.some((code) => code.startsWith('403') || /FORBIDDEN|PERMISSION|NO_DATA_SCOPE/.test(code))
}

export function isApprovalConflict(error) {
  if (serverFailure(error)) return false
  const status = Number(error && (error.status || error.statusCode || error.httpStatus || (error.response && error.response.status)))
  const codes = [error && error.code, error && error.bizCode].map((value) => String(value || '').toUpperCase())
  return status === 409 || codes.some((code) => code.startsWith('409') || code === 'APPROVAL_VERSION_CONFLICT' || code === 'DATA_CONFLICT')
}

function receiptBody(receipt) {
  return receipt && receipt.data && typeof receipt.data === 'object' ? receipt.data : receipt
}

export function hasExplicitApprovalReceipt(receipt, objectId, idFields) {
  const body = receiptBody(receipt)
  if (!body || typeof body !== 'object') return false
  const returnedId = (idFields || []).map((field) => body[field]).find((value) => value != null && value !== '')
  if (String(returnedId == null ? '' : returnedId) !== String(objectId)) return false
  return !!String(body.status || body.currentNode || body.resultStatus || '').trim()
}

export function approvalReceiptChanged(receipt, before) {
  const body = receiptBody(receipt)
  if (!body || typeof body !== 'object') return false
  const prior = before || {}
  const stateChanged = body.status != null && String(body.status) !== String(prior.status == null ? '' : prior.status)
  const nodeChanged = body.currentNode != null && String(body.currentNode) !== String(prior.currentNode == null ? '' : prior.currentNode)
  const versionChanged = body.version != null && String(body.version) !== String(prior.version == null ? '' : prior.version)
  const decisionChanged = body.decisionVersion != null && String(body.decisionVersion) !== String(prior.decisionVersion == null ? '' : prior.decisionVersion)
  return stateChanged || nodeChanged || versionChanged || decisionChanged
}

const APPROVAL_STORAGE_PREFIX = 'teacher-mp:approval-recovery:v1:'
let attemptSequence = 0
const memoryStorage = new Map()
const memoryStorageHost = {
  getStorageSync(key) { return memoryStorage.get(key) || '' },
  setStorageSync(key, value) { memoryStorage.set(key, value) },
  removeStorageSync(key) { memoryStorage.delete(key) }
}

function storageHost() {
  if (typeof uni !== 'undefined') return uni
  if (typeof globalThis !== 'undefined' && globalThis.uni) return globalThis.uni
  return typeof process !== 'undefined' && process.versions && process.versions.node ? memoryStorageHost : null
}

function storageKey(scope, context) {
  return `${APPROVAL_STORAGE_PREFIX}${String(scope || '')}:${encodeURIComponent(String(context || ''))}`
}

function scalar(value) {
  return value == null || ['string', 'number', 'boolean'].includes(typeof value) ? value : undefined
}

function compactAttempt(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw) ||
      !['context', 'scope', 'action', 'attemptKey'].every(field => typeof raw[field] === 'string' && raw[field].trim()) ||
      !['string', 'number'].includes(typeof raw.objectId) || !String(raw.objectId).trim()) return null
  const attempt = {
    attemptKey: raw.attemptKey,
    scope: String(raw.scope),
    context: String(raw.context),
    objectId: String(raw.objectId),
    action: String(raw.action),
    state: 'UNKNOWN'
  }
  const allowed = [
    'beforeStatus', 'beforeNode', 'beforeVersion', 'beforeDecisionVersion', 'beforeStatusVersion', 'beforeTaskId',
    'commandId', 'receiptId', 'requestId', 'operationId'
  ]
  for (const field of allowed) {
    const value = scalar(raw[field])
    if (value !== undefined && value !== null && value !== '') attempt[field] = value
  }
  return attempt
}

function parseStored(value) {
  if (value == null || value === '') return []
  const rows = typeof value === 'string' ? JSON.parse(value) : value
  if (!Array.isArray(rows)) throw new Error('invalid approval recovery storage')
  const clean = rows.map(compactAttempt)
  if (clean.some(row => !row) || new Set(clean.map(row => row.objectId)).size !== clean.length) {
    throw new Error('invalid approval recovery records')
  }
  return clean
}

function readStored(scope, context) {
  const host = storageHost()
  if (!host || typeof host.getStorageSync !== 'function') return { ok: false, attempts: [] }
  try {
    const attempts = parseStored(host.getStorageSync(storageKey(scope, context)))
    if (attempts.some(attempt => attempt.scope !== String(scope) || attempt.context !== String(context))) {
      return { ok: false, attempts: [] }
    }
    return { ok: true, attempts }
  } catch (_) {
    return { ok: false, attempts: [] }
  }
}

function writeStored(scope, context, attempts) {
  const host = storageHost()
  if (!host || typeof host.setStorageSync !== 'function') return false
  const key = storageKey(scope, context)
  const clean = attempts.map(compactAttempt).filter(Boolean)
  try {
    if (!clean.length && typeof host.removeStorageSync === 'function') host.removeStorageSync(key)
    else host.setStorageSync(key, JSON.stringify(clean))
    const checked = readStored(scope, context)
    return checked.ok && JSON.stringify(checked.attempts) === JSON.stringify(clean)
  } catch (_) {
    return false
  }
}

export function createApprovalAttempt(scope, context, objectId, action, before = {}) {
  return compactAttempt({
    attemptKey: `${Date.now().toString(36)}-${(++attemptSequence).toString(36)}-${Math.random().toString(36).slice(2)}`,
    scope, context, objectId, action,
    beforeStatus: before.status,
    beforeNode: before.currentNode,
    beforeTaskId: before.currentTaskId,
    beforeVersion: before.version,
    beforeDecisionVersion: before.decisionVersion,
    beforeStatusVersion: before.statusVersion
  })
}

export function restoreApprovalAttempts(scope, context) {
  return readStored(scope, context)
}

export function persistApprovalAttempt(scope, attempt) {
  const clean = compactAttempt({ ...attempt, scope })
  if (!clean) return false
  const current = readStored(scope, clean.context)
  if (!current.ok) return false
  if (current.attempts.some(item => item.objectId === clean.objectId)) return false
  return writeStored(scope, clean.context, [...current.attempts, clean])
}

export function persistApprovalReceipt(scope, attempt, receipt) {
  const body = receiptBody(receipt) || {}
  const clean = compactAttempt({
    ...attempt,
    scope,
    commandId: body.commandId,
    receiptId: body.receiptId,
    requestId: body.requestId,
    operationId: body.operationId
  })
  if (!clean) return false
  const current = readStored(scope, clean.context)
  if (!current.ok) return false
  const index = current.attempts.findIndex(item => item.objectId === clean.objectId && item.attemptKey === clean.attemptKey)
  if (index < 0) return false
  current.attempts[index] = { ...current.attempts[index], ...clean }
  return writeStored(scope, clean.context, current.attempts)
}

export function clearApprovalAttempt(scope, context, objectId, originalAttempt) {
  if (!originalAttempt || originalAttempt.context !== context || originalAttempt.scope !== scope ||
      String(originalAttempt.objectId) !== String(objectId)) return false
  const current = readStored(scope, context)
  if (!current.ok) return false
  if (!current.attempts.some(attempt => attempt.objectId === String(objectId) && attempt.attemptKey === originalAttempt.attemptKey)) return false
  const remaining = current.attempts.filter((attempt) => attempt.attemptKey !== originalAttempt.attemptKey)
  return writeStored(scope, context, remaining)
}

// Keep the page VM test seam compatible with the original helper import while
// sharing one persistence implementation across all four approval pages.
approvalContextKey.createAttempt = createApprovalAttempt
approvalContextKey.restoreAttempts = restoreApprovalAttempts
approvalContextKey.persistAttempt = persistApprovalAttempt
approvalContextKey.persistReceipt = persistApprovalReceipt
approvalContextKey.clearAttempt = clearApprovalAttempt
