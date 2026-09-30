export function normalizeFormVersion(raw = {}) {
  return {
    formCode: raw.formCode || raw.form_code || '',
    versionId: raw.versionId ?? raw.version_id,
    versionNo: raw.versionNo ?? raw.version_no,
    schemaHash: raw.schemaHash || raw.schema_hash || '',
    supportedClients: raw.supportedClients || raw.supported_clients || [],
    providerCode: raw.providerCode || raw.provider_code || '',
    policyVersion: raw.policyVersion || raw.policy_version || '',
    fields: raw.fields || [],
  }
}

function compare(op, actual, expected) {
  if (op === 'eq') return actual === expected
  if (op === 'neq') return actual !== expected
  if (op === 'in') return Array.isArray(expected) && expected.includes(actual)
  if (op === 'not_in') return !Array.isArray(expected) || !expected.includes(actual)
  if (actual == null || expected == null) return false
  if (op === 'gt') return actual > expected
  if (op === 'gte') return actual >= expected
  if (op === 'lt') return actual < expected
  if (op === 'lte') return actual <= expected
  return false
}

export function evaluateCondition(node, values, depth = 0) {
  if (!node || depth > 8) return false
  if (node.op === 'all' || node.op === 'any') {
    const children = Array.isArray(node.conditions) ? node.conditions : []
    return node.op === 'all'
      ? children.length > 0 && children.every(child => evaluateCondition(child, values, depth + 1))
      : children.some(child => evaluateCondition(child, values, depth + 1))
  }
  return compare(node.op, values[node.field], node.value)
}

export function fieldPresentation(field, values) {
  const visibleWhen = field.visibleWhen || field.visible_when
  const requiredWhen = field.requiredWhen || field.required_when
  const readonlyWhen = field.readonlyWhen || field.readonly_when
  const visible = !visibleWhen || evaluateCondition(visibleWhen, values)
  return {
    visible,
    required: visible && (Boolean(field.required) || evaluateCondition(requiredWhen, values)),
    readonly: Boolean(field.readonly) || evaluateCondition(readonlyWhen, values),
  }
}

export function supportsClient(formVersion, clientType) {
  return normalizeFormVersion(formVersion).supportedClients.includes(clientType)
}
