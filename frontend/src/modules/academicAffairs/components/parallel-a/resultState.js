// Presentation helpers for this group's existing API envelopes; no request or permission policy lives here.
export function isDeniedResult(result) {
  return Number(result?.status) === 403 || String(result?.code || '').startsWith('403') || ['NO_PERMISSION', 'NO_DATA_SCOPE', 'MODULE_NOT_AUTHORIZED', 'MODULE_EXPIRED_READONLY', 'TENANT_CONTEXT_REQUIRED'].includes(result?.bizCode)
}

export function isConflictResult(result) {
  return Number(result?.status) === 409 || String(result?.code || '').startsWith('409') || ['DATA_CONFLICT', 'VERSION_CONFLICT', 'APPROVAL_VERSION_CONFLICT', 'STATE_CONFLICT', 'CONFLICT'].includes(result?.bizCode)
}

export function isMissingResult(result) {
  return Number(result?.status) === 404 || String(result?.code || '').startsWith('404') || ['DATA_NOT_FOUND', 'NOT_FOUND'].includes(result?.bizCode)
}
