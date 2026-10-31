const PREFIX = 'gx_internship_draft:'

export function internshipDraftScope(session, context = []) {
  const identity = session?.identity || {}
  const tenant = session?.realUser?.tenantId || identity.tenantId
  const role = identity.roleCode
  if (!session?.logged || !tenant || !identity.userId || !role) return ''
  return [tenant, identity.userId, role,
    session?.realUser?.currentRole?.contextId || identity.activeContextId || '', ...context]
    .map(value => encodeURIComponent(String(value ?? ''))).join(':')
}

export function readInternshipDraft(session, kind, context = []) {
  const scope = internshipDraftScope(session, context)
  if (!scope) return null
  try {
    const saved = uni.getStorageSync(PREFIX + kind + ':' + scope)
    return saved?.scope === scope ? saved.value : null
  } catch { return null }
}

export function writeInternshipDraft(session, kind, context, value) {
  const scope = internshipDraftScope(session, context)
  if (!scope) return false
  uni.setStorageSync(PREFIX + kind + ':' + scope, { scope, value })
  return true
}
