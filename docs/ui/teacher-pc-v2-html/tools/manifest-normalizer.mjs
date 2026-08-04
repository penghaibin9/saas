import path from 'node:path'

function cleanFieldName(value) {
  return String(value || '').replace(/\?$/, '')
}

function withPrefix(prefix, value) {
  if (!prefix || typeof value !== 'string' || !value) return value
  const normalizedPrefix = String(prefix).replace(/\\/g, '/')
  const normalizedValue = value.replace(/\\/g, '/')
  if (normalizedValue.startsWith(normalizedPrefix)) return normalizedValue
  if (normalizedValue.startsWith('/') || /^[A-Za-z]:\//.test(normalizedValue)) return normalizedValue
  return normalizedValue.includes('/') ? normalizedValue : path.posix.join(normalizedPrefix, normalizedValue)
}

function tupleToObject(fields, tuple) {
  const row = {}
  fields.forEach((field, index) => {
    if (index < tuple.length) row[cleanFieldName(field)] = tuple[index]
  })
  return row
}

function normalizeObject(raw, inheritance = {}) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const row = { ...raw }
  if (!row.html && typeof row.prototype === 'string') row.html = row.prototype
  if (typeof row.html === 'string') row.html = withPrefix(inheritance.htmlPrefix, row.html)
  if (!row.component && inheritance.componentPrefix && typeof raw.component === 'string') {
    row.component = withPrefix(inheritance.componentPrefix, raw.component)
  }
  if (row.permissionKey === undefined && inheritance.permissionKey !== undefined) {
    row.permissionKey = inheritance.permissionKey
  }
  if (row.permissionAny === undefined && inheritance.permissionAny !== undefined) {
    row.permissionAny = inheritance.permissionAny
  }
  if (row.sharedPrototype === undefined && inheritance.sharedPrototype !== undefined) {
    row.sharedPrototype = inheritance.sharedPrototype
  }
  if (row.center === undefined && inheritance.center !== undefined) row.center = inheritance.center
  if (row.workspace === undefined && inheritance.workspace !== undefined) row.workspace = inheritance.workspace
  if (row.statesCovered === undefined && inheritance.statesCovered !== undefined) {
    row.statesCovered = inheritance.statesCovered
  }
  return typeof row.route === 'string' && typeof row.html === 'string' ? row : null
}

function normalizeArrayRows(rows, fields, inheritance) {
  const entries = []
  for (const item of rows) {
    const raw = Array.isArray(item) && fields.length ? tupleToObject(fields, item) : item
    const normalized = normalizeObject(raw, inheritance)
    if (normalized) entries.push(normalized)
  }
  return entries
}

export function normalizeManifestPart(part) {
  if (Array.isArray(part)) {
    return { entries: normalizeArrayRows(part, [], {}), sharedAssets: [] }
  }
  if (!part || typeof part !== 'object') return { entries: [], sharedAssets: [] }

  const inheritance = part.inheritance && typeof part.inheritance === 'object' ? part.inheritance : {}
  const fields = Array.isArray(part.entryFields) ? part.entryFields : []
  const rowCollections = [part.entries, part.routes, part.records].filter(Array.isArray)
  const entries = rowCollections.flatMap((rows) => normalizeArrayRows(rows, fields, inheritance))
  const sharedAssets = Array.isArray(part.sharedAssets) ? part.sharedAssets : []
  return { entries, sharedAssets }
}
