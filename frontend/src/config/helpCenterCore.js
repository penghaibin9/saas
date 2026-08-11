import './help/helpRoleGuidanceRuntime.js'

/**
 * 帮助筛选只决定“优先给谁看”，不参与后端授权。
 * 保留原 5 个粗粒度入口兼容 authRole 自动映射，同时增加老师真实会使用的细分筛选。
 */
export const HELP_ROLE_OPTIONS = [
  { value: 'all', label: '全部角色' },
  { value: 'school-admin', label: '学校管理员' },
  { value: 'academic', label: '教务人员（全部）' },
  { value: 'academic-admin', label: '教务处管理员' },
  { value: 'college-admin', label: '学院管理员' },
  { value: 'student-affairs', label: '学工人员（全部）' },
  { value: 'counselor', label: '辅导员 / 班主任' },
  { value: 'student-affairs-admin', label: '学工处管理员' },
  { value: 'psychology-teacher', label: '心理老师' },
  { value: 'funding-teacher', label: '资助老师' },
  { value: 'teacher', label: '教师 / 指导教师（全部）' },
  { value: 'course-teacher', label: '任课 / 录分教师' },
  { value: 'internship-mentor', label: '实习指导 / 企业导师' },
  { value: 'graduation-role', label: '毕设导师 / 评阅 / 答辩' },
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

/**
 * 细分角色只做推荐过滤。这里故意不塞进 ROLE_ALIASES：
 * resolveHelpRole(authRole) 仍稳定返回原来的粗粒度角色，避免帮助 UI 反向影响认证语义。
 */
const FINE_ROLE_FILTERS = Object.freeze({
  'academic-admin': /^(academic_admin|teaching_admin|教务人员|教务管理员|教务处管理员)$/i,
  'college-admin': /^(college_admin|学院管理员|学院教务|学院学工|院领导)$/i,
  counselor: /^(counselor|head_teacher|class_teacher|辅导员|班主任)$/i,
  'student-affairs-admin': /^(student_affairs_admin|学工人员|学工管理员|学工处管理员|学生处管理员)$/i,
  'psychology-teacher': /^(psychology_teacher|心理老师)$/i,
  'funding-teacher': /^(funding_teacher|资助老师)$/i,
  'course-teacher': /^(academic_teacher|course_teacher|grade_teacher|任课教师|录分教师)$/i,
  'internship-mentor': /^(intern_mentor|internship_teacher|enterprise_mentor|实习指导教师|实习指导老师|企业导师)$/i,
  'graduation-role': /^(graduation_admin|graduation_teacher|gd_college_admin|gd_major_admin|gd_mentor|gd_reviewer|gd_defense_secretary|gd_defense_expert|gd_grade_admin|毕业设计指导教师|毕业设计指导老师|毕设指导教师|毕设导师|毕设管理员|评阅教师|答辩秘书|答辩专家|答辩评委)$/i
})

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
  const selected = String(selectedRole || 'all').trim().toLowerCase()
  const tokens = getHelpRoleTokens(item)

  // 用户主动选择细分角色时，按任务卡原始角色文本做相关性收敛；
  // 没有角色元数据的通用帮助仍显示，避免公共故障卡被误隐藏。
  const fineMatcher = FINE_ROLE_FILTERS[selected]
  if (fineMatcher) {
    if (!tokens.length) return true
    return tokens.some((token) => fineMatcher.test(String(token).trim()))
  }

  const role = normalizeHelpRole(selectedRole) || 'all'
  if (role === 'all' || role === 'school-admin') return true
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
