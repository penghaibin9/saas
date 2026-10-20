import { academicErrorKind } from './studentAcademicUi.js'

// A 5xx or an unclassified transport response does not prove the command failed.
export function studentAcademicWriteErrorKind(error) {
  const status = Number(error?.httpStatus || error?.status || error?.statusCode)
  // The HTTP status is authoritative; the backend may use its generic 500001 envelope for a 409 domain rejection.
  if (status >= 500 && status < 600) return 'network'
  if (status === 403) return 'forbidden'
  if (status === 409) return 'conflict'
  if (status >= 400 && status < 500) return 'error'
  const values = [error?.bizCode, error?.code]
  if (values.some(value => { const code = Number(value); return (code >= 500 && code < 600) || (code >= 500000 && code < 600000) })) return 'network'
  const kind = academicErrorKind(error)
  if (kind !== 'error') return kind
  return (status >= 400 && status < 500) || error?.biz === true ? 'error' : 'network'
}

export function studentAcademicIdentity(session) {
  const user = session?.user || {}
  if (!user.userId && !user.studentNo) return ''
  return [
    user.tenantId || user.tenantCode || session?.tenantId || session?.tenantCode || '',
    user.userId || user.studentNo || '',
    user.activeContextId || session?.activeContextId || user.currentContextId || session?.currentContextId || session?.currentRole?.contextId || '',
    user.currentRoleCode || user.roleCode || user.currentRole?.roleCode || '',
    user.userType || ''
  ].map(String).join(':')
}

export function exactPositiveDecimalId(value) {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) return ''
  const text = String(value ?? '')
  return /^[1-9]\d*$/.test(text) ? text : ''
}

const PERSISTENCE_VERSION = 2
const MAX_PENDING_COMMANDS = 16
let fallbackCommandSequence = 0

function memoryStorage() {
  const entries = new Map()
  return { getItem: (key) => entries.has(key) ? entries.get(key) : null, setItem: (key, value) => entries.set(key, value), removeItem: (key) => entries.delete(key) }
}

function browserStorage(fallback) {
  try {
    if (globalThis.localStorage) return { ok: true, storage: globalThis.localStorage }
    if (typeof window === 'undefined') return { ok: true, storage: fallback }
    return { ok: false, error: 'STORAGE_UNAVAILABLE' }
  } catch { return { ok: false, error: 'STORAGE_UNAVAILABLE' } }
}

function safeReferencePart(value, { required = false, max = 128 } = {}) {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) return ''
  const text = String(value ?? '').trim()
  if (!text) return required ? '' : ''
  const hasControlCharacter = [...text].some((character) => {
    const code = character.charCodeAt(0)
    return code <= 31 || code === 127
  })
  if (text.length > max || hasControlCharacter) return ''
  return text
}

function newCommandKey() {
  try {
    if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  } catch { /* use the local non-secret uniqueness fallback */ }
  fallbackCommandSequence += 1
  return `${Date.now().toString(36)}-${fallbackCommandSequence.toString(36)}-${Math.random().toString(36).slice(2)}`
}

function normalizePersistentReference(value, identity, context) {
  const storedIdentity = safeReferencePart(value?.identity, { required: true, max: 512 })
  const storedContext = safeReferencePart(value?.context, { required: true, max: 48 })
  const commandKey = safeReferencePart(value?.commandKey, { required: true })
  const action = safeReferencePart(value?.action, { required: true, max: 48 })
  const objectId = safeReferencePart(value?.objectId, { required: true })
  if (Number(value?.version) !== PERSISTENCE_VERSION || !identity || !context || storedIdentity !== identity || storedContext !== context || !commandKey || !action || !objectId) return null
  return Object.freeze({
    version: PERSISTENCE_VERSION,
    identity: storedIdentity,
    context: storedContext,
    commandKey,
    action,
    objectId,
    parentId: safeReferencePart(value?.parentId),
    ackId: safeReferencePart(value?.ackId)
  })
}

export function createStudentAcademicCommandGuard(readIdentity, persistenceContext = '') {
  let commandEpoch = 0
  let readGeneration = 0
  const readEpochs = new Map()
  let disposed = false
  const fallbackStorage = memoryStorage()
  const identity = () => String(readIdentity?.() || '')
  const context = safeReferencePart(persistenceContext, { max: 48 })
  const persistenceKey = () => context && identity()
    ? `sp-academic-command-v${PERSISTENCE_VERSION}:${encodeURIComponent(context)}:${encodeURIComponent(identity())}`
    : ''
  const readPersistent = () => {
    const expectedIdentity = identity()
    const key = persistenceKey()
    const storageResult = browserStorage(fallbackStorage)
    if (!key) return { ok: false, error: 'IDENTITY_OR_CONTEXT_UNAVAILABLE', items: [] }
    if (!storageResult.ok) return { ok: false, error: storageResult.error, items: [] }
    try {
      const raw = storageResult.storage.getItem(key)
      if (raw == null) return { ok: true, error: '', items: [] }
      const value = JSON.parse(raw)
      if (!Array.isArray(value) || value.length > MAX_PENDING_COMMANDS) return { ok: false, error: 'STORAGE_CORRUPTED', items: [] }
      const items = value.map((item) => normalizePersistentReference(item, expectedIdentity, context))
      if (items.some((item) => !item) || new Set(items.map((item) => item.commandKey)).size !== items.length) return { ok: false, error: 'STORAGE_CORRUPTED', items: [] }
      return { ok: true, error: '', items }
    } catch { return { ok: false, error: 'STORAGE_CORRUPTED', items: [] } }
  }
  const writePersistent = (items, expectedIdentity) => {
    if (!expectedIdentity || expectedIdentity !== identity() || items.length > MAX_PENDING_COMMANDS) return false
    const key = persistenceKey()
    const storageResult = browserStorage(fallbackStorage)
    if (!key || !storageResult.ok) return false
    const normalized = items.map((item) => normalizePersistentReference(item, expectedIdentity, context))
    if (normalized.some((item) => !item) || new Set(normalized.map((item) => item.commandKey)).size !== normalized.length) return false
    try {
      if (normalized.length) storageResult.storage.setItem(key, JSON.stringify(normalized))
      else storageResult.storage.removeItem(key)
      const verified = readPersistent()
      return verified.ok && JSON.stringify(verified.items) === JSON.stringify(normalized)
    } catch { return false }
  }
  const sameObject = (left, right) => left.action === right.action && left.objectId === right.objectId && left.parentId === right.parentId
  const sameHandle = (left, right) => left.commandKey === right.commandKey && left.identity === right.identity && left.context === right.context && sameObject(left, right)
  const exposePersistent = (result) => {
    const items = result.ok ? [...result.items] : []
    Object.defineProperty(items, 'persistenceError', { value: result.error || '', enumerable: false })
    return Object.freeze(items)
  }

  return {
    beginCommand(payload) {
      return Object.freeze({ ...payload, epoch: ++commandEpoch, identity: identity() })
    },
    beginRead(scope = 'page') {
      const key = String(scope || 'page')
      const epoch = (readEpochs.get(key) || 0) + 1
      readEpochs.set(key, epoch)
      return Object.freeze({ scope: key, epoch, generation: readGeneration, identity: identity() })
    },
    isCurrentCommand(command) {
      return !disposed && command?.epoch === commandEpoch && command?.identity === identity()
    },
    isCurrentRead(read) {
      return !disposed && read?.generation === readGeneration && read?.epoch === readEpochs.get(read?.scope) && read?.identity === identity()
    },
    pendingCommands() {
      return exposePersistent(readPersistent())
    },
    persistenceState() {
      const result = readPersistent()
      return Object.freeze({ ok: result.ok, error: result.error, count: result.items.length })
    },
    preparePersistentCommand(reference) {
      const expectedIdentity = identity()
      const current = readPersistent()
      if (!current.ok || current.items.length >= MAX_PENDING_COMMANDS) return null
      const normalized = normalizePersistentReference({ ...reference, version: PERSISTENCE_VERSION, identity: expectedIdentity, context, commandKey: newCommandKey() }, expectedIdentity, context)
      if (!normalized) return null
      if (current.items.some((item) => sameObject(item, normalized))) return null
      return writePersistent([...current.items, normalized], expectedIdentity) ? normalized : null
    },
    rememberPersistentAck(reference, ackId) {
      const expectedIdentity = identity()
      if (reference?.identity !== expectedIdentity || reference?.context !== context) return null
      const normalized = normalizePersistentReference({ ...reference, ackId }, expectedIdentity, context)
      if (!normalized || !normalized.ackId) return null
      const current = readPersistent()
      if (!current.ok) return null
      const index = current.items.findIndex((item) => sameHandle(item, normalized))
      if (index < 0) return null
      const next = [...current.items]
      next[index] = normalized
      return writePersistent(next, expectedIdentity) ? normalized : null
    },
    completePersistentCommand(reference) {
      const expectedIdentity = identity()
      if (reference?.identity !== expectedIdentity || reference?.context !== context) return false
      const normalized = normalizePersistentReference(reference, expectedIdentity, context)
      if (!normalized) return false
      const current = readPersistent()
      if (!current.ok || !current.items.some((item) => sameHandle(item, normalized))) return false
      return writePersistent(current.items.filter((item) => !sameHandle(item, normalized)), expectedIdentity)
    },
    invalidate() {
      commandEpoch += 1
      readGeneration += 1
    },
    dispose() {
      disposed = true
      commandEpoch += 1
      readGeneration += 1
    }
  }
}

export async function readStudentAcademicSnapshot(guard, reader, scope = 'page') {
  const ticket = guard.beginRead(scope)
  try {
    const value = await reader()
    return guard.isCurrentRead(ticket)
      ? { ok: true, value, ticket }
      : { ok: false, stale: true, ticket }
  } catch (error) {
    return guard.isCurrentRead(ticket)
      ? { ok: false, error, ticket }
      : { ok: false, stale: true, ticket }
  }
}
