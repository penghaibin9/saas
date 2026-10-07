import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const STORAGE_KEY = 'gx_academic_pending_commands_v1'
const SESSION_KEY = 'gx_session_v1'
const APPLICATION_SCOPES = new Set(['evaluation', 'exam', 'level-exam', 'makeup', 'recheck', 'recognition', 'registration', 'status', 'textbook'])

let generation = currentSessionGeneration()
let ownerKey = ''
let entries = new Map()
let sequence = 0

const clone = value => value == null ? value : JSON.parse(JSON.stringify(value))
const text = value => value == null ? '' : String(value).trim().slice(0, 160)

function hash(value, seed) {
  let result = seed >>> 0
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index)
    result = Math.imul(result, 0x01000193) >>> 0
  }
  return result.toString(36)
}

function currentOwner() {
  try {
    const raw = uni.getStorageSync(SESSION_KEY)
    const session = typeof raw === 'string' ? JSON.parse(raw) : raw
    const identity = session && session.identity || {}
    const tenant = text(identity.tenantId)
    const user = text(identity.userId)
    const role = text(identity.roleCode || session && session.currentRole)
    const context = text(identity.activeContextId)
    const student = text(identity.studentId || identity.studentNo)
    if (!session || session.logged !== true || !tenant || !user || !role || !context) return null
    const source = [tenant, user, role, context, student].join('\u001f')
    // The storage key contains only two deterministic digests, never raw identity values or credentials.
    return `i-${hash(source, 0x811c9dc5)}-${hash(source, 0x9e3779b9)}`
  } catch (_) {
    return null
  }
}

function syncRuntime() {
  const nextGeneration = currentSessionGeneration()
  const nextOwner = currentOwner() || ''
  if (generation !== nextGeneration || ownerKey !== nextOwner) {
    generation = nextGeneration
    ownerKey = nextOwner
    entries = new Map()
  }
  return nextOwner
}

function readStore() {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (!raw) return { version: 1, owners: {} }
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return parsed && parsed.version === 1 && parsed.owners && typeof parsed.owners === 'object'
      ? parsed
      : null
  } catch (_) {
    return null
  }
}

function writeStore(store) {
  try {
    const serialized = JSON.stringify(store)
    uni.setStorageSync(STORAGE_KEY, serialized)
    const readBack = uni.getStorageSync(STORAGE_KEY)
    return String(readBack || '') === serialized
  } catch (_) {
    return false
  }
}

function commandId() {
  sequence += 1
  return `aa-${Date.now().toString(36)}-${sequence.toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function allowedRecovery(value) {
  if (!value || typeof value !== 'object') return null
  const field = text(value.field)
  if (!['status', 'registrationStatus', 'submitted'].includes(field)) return null
  const result = { field }
  if (value.equals !== undefined) result.equals = typeof value.equals === 'boolean' ? value.equals : text(value.equals)
  if (Array.isArray(value.excludes)) result.excludes = value.excludes.map(text).filter(Boolean).slice(0, 8)
  return Object.keys(result).length > 1 ? result : null
}

function applicationReference(value) {
  if (!value || !text(value.commandId) || text(value._pendingOwner) !== ownerKey) return null
  return {
    commandId: text(value.commandId),
    action: text(value.action || value.scope),
    kind: text(value.kind),
    recordKey: text(value.recordKey || value.idKey),
    receiptKey: text(value.receiptKey || value.idKey),
    objectId: text(value.existingId || value.objectId),
    returnedId: text(value.returnedId),
    recovery: allowedRecovery(value.recovery)
  }
}

function selectionReference(value) {
  const result = {}
  for (const [key, item] of Object.entries(value || {})) {
    if (!item || !text(item.commandId) || text(item._pendingOwner) !== ownerKey) continue
    const operation = text(item.operation).toUpperCase()
    const course = text(item.selectionCourseId)
    const batch = text(item.batchId)
    if (!['ENROLL', 'DROP'].includes(operation) || !course || !batch) continue
    result[text(key)] = {
      commandId: text(item.commandId), action: operation, selectionCourseId: course,
      selectionRecordId: text(item.selectionRecordId), batchId: batch, returnedId: text(item.returnedId)
    }
  }
  return Object.keys(result).length ? result : null
}

function majorSplitReference(value) {
  const result = {}
  for (const [key, item] of Object.entries(value || {})) {
    if (!item || !text(item.commandId) || text(item._pendingOwner) !== ownerKey) continue
    const batchId = text(item.batchId || key)
    const choices = Array.isArray(item.choices) ? item.choices.map(text).filter(Boolean).slice(0, 12) : []
    if (!batchId || !choices.length) continue
    result[batchId] = {
      commandId: text(item.commandId), action: 'MAJOR_SPLIT_SUBMIT', batchId,
      volunteerId: text(item.volunteerId), choiceIds: choices
    }
  }
  return Object.keys(result).length ? result : null
}

function serializeCommand(scope, value) {
  if (APPLICATION_SCOPES.has(scope)) return applicationReference(value)
  if (scope === 'selection') return selectionReference(value)
  if (scope === 'major-split') return majorSplitReference(value)
  return null
}

function hydrateCommand(scope, value) {
  if (!value) return null
  if (APPLICATION_SCOPES.has(scope)) return { ...clone(value), recoveryOnly: true, _pendingOwner: ownerKey }
  if (scope === 'selection') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, {
      commandId: item.commandId, operation: item.action, selectionCourseId: item.selectionCourseId,
      selectionRecordId: item.selectionRecordId, batchId: item.batchId, returnedId: item.returnedId,
      recoveryOnly: true, _pendingOwner: ownerKey
    }]))
  }
  if (scope === 'major-split') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, {
      commandId: item.commandId, batchId: item.batchId, volunteerId: item.volunteerId,
      choices: item.choiceIds || [], recoveryOnly: true, _pendingOwner: ownerKey
    }]))
  }
  return null
}

function commandMatchesStored(scope, command) {
  const owner = syncRuntime()
  if (!owner || !command || text(command._pendingOwner) !== owner || !text(command.commandId)) return false
  const stored = readStore()?.owners?.[owner]?.scopes?.[scope]
  if (APPLICATION_SCOPES.has(scope)) return text(stored?.commandId) === text(command.commandId)
  return Object.values(stored || {}).some(item => text(item.commandId) === text(command.commandId))
}

// Commands are born with a stable origin marker. A caller must persist it before it may POST.
export function createPendingCommand(scope, value = {}) {
  const owner = syncRuntime()
  if (!owner || (!APPLICATION_SCOPES.has(scope) && scope !== 'selection' && scope !== 'major-split')) return null
  return { ...clone(value), commandId: commandId(), _pendingOwner: owner, action: value.action || scope }
}

export function canUpdatePendingCommand(scope, command) {
  return commandMatchesStored(scope, command)
}

// Keep only the command reference after a permission denial. Request bodies stay process-memory-only.
export function redactPendingCommand(scope, command) {
  const owner = syncRuntime()
  if (!owner || !command || text(command._pendingOwner) !== owner) return null
  if (APPLICATION_SCOPES.has(scope)) {
    const reference = applicationReference(command)
    if (!reference) return null
    const redacted = { ...reference, recoveryOnly: true, _pendingOwner: owner }
    entries.set(scope, clone(redacted))
    return redacted
  }
  return null
}

// Drafts remain process-memory-only. Formal command references are persisted per real session identity.
export function readPending(scope) {
  const owner = syncRuntime()
  const memory = entries.get(scope)
  if (memory) return clone(memory)
  if (scope.startsWith('draft:') || !owner) return null
  const stored = readStore()?.owners?.[owner]?.scopes?.[scope]
  const hydrated = hydrateCommand(scope, stored)
  if (hydrated) entries.set(scope, clone(hydrated))
  return hydrated ? clone(hydrated) : null
}

export function savePending(scope, value) {
  const owner = syncRuntime()
  if (scope.startsWith('draft:')) {
    if (value && Object.keys(value).length) entries.set(scope, clone(value))
    else entries.delete(scope)
    return true
  }
  if (!owner) return false
  const store = readStore()
  if (!store) return false
  const ownerEntry = store.owners[owner] || { scopes: {} }
  const scopes = { ...(ownerEntry.scopes || {}) }
  if (value && Object.keys(value).length) {
    const reference = serializeCommand(scope, value)
    if (!reference) return false
    scopes[scope] = reference
  } else {
    delete scopes[scope]
  }
  store.owners = { ...store.owners, [owner]: { scopes } }
  if (!writeStore(store)) return false
  if (value && Object.keys(value).length) entries.set(scope, clone(value))
  else entries.delete(scope)
  return true
}
