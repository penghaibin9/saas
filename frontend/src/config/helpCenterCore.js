import './help/helpRoleGuidanceRuntime.js'

export const HELP_ROLE_OPTIONS = [
  { value: 'all', label: '全部角色' },
  { value: 'school-admin', label: '学校管理员' },
  { value: 'academic', label: '教务人员' },
  { value: 'student-affairs', label: '学工人员 / 辅导员' },
  { value: 'teacher', label: '教师 / 指导教师' },
  { value: 'student', label: '学生' }
]

const ROLE_ALIASES = new Map([
  ['all', 'all'], ['全部', 'all'], ['所有角色', 'all'],
  ['admin', 'school-admin'], ['administrator', 'school-admin'],
  ['school-admin', 'school-admin'], ['school_admin', 'school-admin'], ['schooladmin', 'school-admin'],
  ['super_admin', 'school-admin'], ['platform_admin', 'school-admin'], ['system_admin', 'school-admin'],
  ['school_admin', 'school-admin'], ['sys_admin', 'school-admin'], ['security_auditor', 'school-admin'],
  ['leader', 'school-admin'], ['school_leader', 'school-admin'], ['college_admin', 'school-admin'],
  ['学校管理员', 'school-admin'], ['平台运营人员', 'school-admin'], ['管理员', 'school-admin'],
  ['安全审计员', 'school-admin'], ['校领导', 'school-admin'], ['院领导', 'school-admin'], ['学院管理员', 'school-admin'],
  ['教务', 'academic'], ['教务人员', 'academic'], ['教务管理员', 'academic'],
  ['academic', 'academic'], ['academic_admin', 'academic'], ['teaching_admin', 'academic'],
  ['教务处管理员', 'academic'],
  ['学工', 'student-affairs'], ['学工人员', 'student-affairs'], ['学工管理员', 'student-affairs'],
  ['student-affairs', 'student-affairs'], ['student_affairs', 'student-affairs'], ['student_affairs_admin', 'student-affairs'],
  ['counselor', 'student-affairs'], ['辅导员', 'student-affairs'], ['班主任', 'student-affairs'],
  ['head_teacher', 'student-affairs'], ['class_teacher', 'student-affairs'],
  ['psychology_teacher', 'student-affairs'], ['funding_teacher', 'student-affairs'], ['youth_league', 'student-affairs'],
  ['dorm_manager', 'student-affairs'], ['org_personnel', 'student-affairs'],
  ['心理老师', 'student-affairs'], ['资助老师', 'student-affairs'], ['团委老师', 'student-affairs'], ['宿管', 'student-affairs'],
  ['teacher', 'teacher'], ['教师', 'teacher'], ['任课教师', 'teacher'], ['指导教师', 'teacher'], ['导师', 'teacher'],
  ['academic_teacher', 'teacher'], ['intern_mentor', 'teacher'], ['employment_teacher', 'teacher'],
  ['graduation_admin', 'teacher'], ['gd_college_admin', 'teacher'], ['gd_major_admin', 'teacher'],
  ['gd_mentor', 'teacher'], ['gd_reviewer', 'teacher'], ['gd_defense_secretary', 'teacher'],
  ['gd_defense_expert', 'teacher'], ['gd_grade_admin', 'teacher'],
  ['实习指导教师', 'teacher'], ['毕业设计指导教师', 'teacher'], ['毕设管理员', 'teacher'],
  ['实习指导老师', 'teacher'], ['就业教师', 'teacher'],
  ['internship_teacher', 'teacher'], ['graduation_teacher', 'teacher'],
  ['enterprise_mentor', 'teacher'], ['企业导师', 'teacher'],
  ['student', 'student'], ['学生', 'student']
])

const ROLE_VISIBILITY = {
  academic: new Set(['academic', 'teacher']),
  'student-affairs': new Set(['student-affairs', 'teacher']),
  teacher: new Set(['teacher']),
  student: new Set(['student'])
}

export function tokenizeHelpRoles(value) {
  const source = Array.isArray(value) ? value : value ? [value] : []
  return source
    .flatMap((item) => String(item).split(/[、,，/|]+/))
    .map((item) => item.trim())
    .filter(Boolean)
}

export function normalizeHelpRole(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const key = raw.toLowerCase().replace(/\s+/g, '_')
  if (ROLE_ALIASES.has(key)) return ROLE_ALIASES.get(key)
  if (ROLE_ALIASES.has(raw)) return ROLE_ALIASES.get(raw)
  if (/超级|平台|学校.*管理员|系统.*管理员|学院管理员|领导|审计/.test(raw)) return 'school-admin'
  if (/教务|教学管理/.test(raw)) return 'academic'
  if (/学工|学生处|学生工作|辅导员|班主任|心理|资助|团委|宿管/.test(raw)) return 'student-affairs'
  if (/教师|导师|指导|答辩|评阅/.test(raw)) return 'teacher'
  if (/学生/.test(raw)) return 'student'
  return ''
}

export function resolveHelpRole(authRole, authLabel = '') {
  return normalizeHelpRole(authRole) || normalizeHelpRole(authLabel) || 'all'
}

export function getHelpRoleTokens(item) {
  return tokenizeHelpRoles(item?.roles ?? item?.role)
}

export function isHelpVisibleForRole(item, selectedRole = 'all') {
  const role = normalizeHelpRole(selectedRole) || 'all'
  if (role === 'all' || role === 'school-admin') return true
  const tokens = getHelpRoleTokens(item)
  if (!tokens.length) return true
  const normalized = tokens.map(normalizeHelpRole).filter(Boolean)
  // 帮助筛选只做相关性推荐，不是授权边界。真正能否操作以后端 permissionCode + 数据范围 + 业务关系 + 状态机为准。
  // 旧条目角色是自由文本；无法识别时宽松显示，避免误隐藏。
  if (!normalized.length || normalized.includes('all')) return true
  const allowed = ROLE_VISIBILITY[role] || new Set([role])
  return normalized.some((candidate) => allowed.has(candidate))
}

export function collectHelpStrings(value, output = []) {
  if (typeof value === 'string') output.push(value)
  else if (Array.isArray(value)) value.forEach((item) => collectHelpStrings(item, output))
  else if (value && typeof value === 'object') Object.values(value).forEach((item) => collectHelpStrings(item, output))
  return output
}

export function buildHelpSearchText(item) {
  return collectHelpStrings({
    title: item?.title,
    summary: item?.summary,
    keywords: item?.keywords,
    roles: item?.roles || item?.role,
    roleGuidance: item?.roleGuidance,
    authorizationPrinciple: item?.authorizationPrinciple,
    platforms: item?.platforms,
    module: item?.module,
    category: item?.category,
    entry: item?.entry,
    route: item?.route,
    mobilePath: item?.mobilePath,
    prerequisites: item?.prerequisites,
    permissions: item?.permissions,
    permissionNotes: item?.permissionNotes,
    steps: item?.steps,
    points: item?.points,
    tips: item?.tips,
    warnings: item?.warnings,
    fields: item?.fields,
    successCriteria: item?.successCriteria,
    troubleshooting: item?.troubleshooting,
    faq: item?.faq,
    related: item?.related,
    sections: item?.sections
  }).join(' ').toLowerCase()
}

export function uniqueHelpEntries(entries) {
  const seen = new Set()
  return entries.filter((entry) => {
    if (!entry?.item?.id || seen.has(entry.item.id)) return false
    seen.add(entry.item.id)
    return true
  })
}
