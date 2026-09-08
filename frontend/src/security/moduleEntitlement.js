/**
 * Commercial/module entitlement projection shared by menu and route UX gates.
 *
 * This is defense-in-depth only: backend module_access_service remains the security
 * boundary. ``moduleEntitlements=null`` means the authority has not been loaded yet;
 * ``healthy=false`` means the authority is unavailable and must be surfaced as a
 * service error rather than mislabelled as "not purchased".
 */
export const MODULE_CODE_TO_KEYS = Object.freeze({
  STUDENT: ['studentProfile', 'student360', 'student', 'STUDENT'],
  STUDENT_AFFAIRS: ['studentAffairs', 'STUDENT_AFFAIRS'],
  INTERNSHIP: ['internship', 'INTERNSHIP'],
  GRADUATION: ['graduationDesign', 'graduation', 'GRADUATION'],
  ACADEMIC_AFFAIRS: ['academicAffairs', 'academicLegacy', 'ACADEMIC_AFFAIRS'],
  CAMPUS_SERVICE: ['campusService', 'CAMPUS_SERVICE'],
  EMPLOYMENT: ['employment', 'EMPLOYMENT'],
  ORIENTATION: ['orientation', 'ORIENTATION'],
  SYSTEM: ['systemAdmin', 'system', 'SYSTEM', 'auditLog'],
  WORKBENCH: ['workbench', 'todoMessage', 'WORKBENCH', 'approval'],
  APPROVAL: ['approval', 'workbench', 'todoMessage', 'APPROVAL'],
  PLATFORM: ['platform', 'PLATFORM', 'apiAccess']
})

export const CORE_GROUP_ENTITLEMENT = Object.freeze({
  'student-affairs': ['studentAffairs'],
  'academic-affairs': ['academicAffairs', 'academicLegacy'],
  graduation: ['graduationDesign', 'graduation'],
  internship: ['internship']
})

export function moduleCodeForNav(groupKey, path) {
  const p = String(path || '')
  if (p.startsWith('/admin/orientation')) return 'ORIENTATION'
  if (p.startsWith('/admin/campus-service')) return 'CAMPUS_SERVICE'
  if (p.startsWith('/admin/data-center')) return 'WORKBENCH'
  if (p.startsWith('/admin/approval')) return 'APPROVAL'
  if (p.startsWith('/admin/employment')) return 'EMPLOYMENT'
  if (p.startsWith('/admin/workflow')) return 'SYSTEM'
  if (p.startsWith('/admin/platform')) return 'PLATFORM'
  if (p === '/workbench' || p.startsWith('/admin/messages') || p.startsWith('/admin/help')) return 'WORKBENCH'
  const map = {
    workbench: 'WORKBENCH',
    'student-affairs': 'STUDENT_AFFAIRS',
    'academic-affairs': 'ACADEMIC_AFFAIRS',
    graduation: 'GRADUATION',
    internship: 'INTERNSHIP',
    system: 'SYSTEM',
    platform: 'PLATFORM'
  }
  return map[groupKey] || 'WORKBENCH'
}

export function moduleEntitled(moduleCode, entitlements, healthy = true) {
  if (healthy === false) return true
  if (!Array.isArray(entitlements)) return true
  if (entitlements.includes('*')) return true
  const keys = MODULE_CODE_TO_KEYS[moduleCode] || [moduleCode, String(moduleCode || '').toLowerCase()]
  return keys.some((key) => entitlements.includes(key))
}

export function coreGroupEntitled(groupKey, entitlements, healthy = true) {
  if (healthy === false) return true
  if (!Array.isArray(entitlements)) return true
  if (entitlements.includes('*')) return true
  const required = CORE_GROUP_ENTITLEMENT[groupKey]
  if (!required) return true
  return required.some((key) => entitlements.includes(key))
}

export function entitlementSignature(entitlements, healthy = true) {
  if (healthy === false) return '__module_authority_unhealthy__'
  if (!Array.isArray(entitlements)) return '__module_authority_unknown__'
  return [...new Set(entitlements.map((value) => String(value)))].sort().join(',')
}
