export function roleAssignmentSignature(assignments = []) {
  return JSON.stringify(assignments.map(item => ({
    roleCode: item.roleCode,
    scopeType: item.scopeType,
    scopeIds: [...new Set((item.scopeIds || []).map(String))].sort()
  })).sort((a, b) => a.roleCode.localeCompare(b.roleCode)))
}

export function accountDetailsChanged(value, original) {
  return ['name', 'phone'].some(key => String(value?.[key] || '') !== String(original?.[key] || ''))
}
