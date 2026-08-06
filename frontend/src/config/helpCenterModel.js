import {
  HELP_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  HELP_SECTIONS,
  getHelpById
} from './helpContent'

const TYPE_LABELS = {
  card: '帮助任务卡',
  doc: '功能帮助',
  flow: '业务流程图'
}

export const HELP_ROLE_OPTIONS = [
  { value: 'all', label: '全部角色' },
  { value: 'school-admin', label: '学校管理员' },
  { value: 'academic', label: '教务人员' },
  { value: 'student-affairs', label: '学工人员 / 辅导员' },
  { value: 'teacher', label: '教师 / 指导教师' },
  { value: 'student', label: '学生' }
]

const ROLE_ALIASES = new Map([
  ['all', 'all'],
  ['全部', 'all'],
  ['所有角色', 'all'],
  ['admin', 'school-admin'],
  ['administrator', 'school-admin'],
  ['school-admin', 'school-admin'],
  ['school_admin', 'school-admin'],
  ['schooladmin', 'school-admin'],
  ['super_admin', 'school-admin'],
  ['platform_admin', 'school-admin'],
  ['system_admin', 'school-admin'],
  ['学校管理员', 'school-admin'],
  ['平台运营人员', 'school-admin'],
  ['管理员', 'school-admin'],
  ['教务', 'academic'],
  ['教务人员', 'academic'],
  ['教务管理员', 'academic'],
  ['academic', 'academic'],
  ['academic_admin', 'academic'],
  ['teaching_admin', 'academic'],
  ['学工', 'student-affairs'],
  ['学工人员', 'student-affairs'],
  ['学工管理员', 'student-affairs'],
  ['student-affairs', 'student-affairs'],
  ['student_affairs', 'student-affairs'],
  ['counselor', 'student-affairs'],
  ['辅导员', 'student-affairs'],
  ['班主任', 'student-affairs'],
  ['head_teacher', 'student-affairs'],
  ['class_teacher', 'student-affairs'],
  ['teacher', 'teacher'],
  ['教师', 'teacher'],
  ['任课教师', 'teacher'],
  ['指导教师', 'teacher'],
  ['导师', 'teacher'],
  ['实习指导教师', 'teacher'],
  ['毕业设计指导教师', 'teacher'],
  ['internship_teacher', 'teacher'],
  ['graduation_teacher', 'teacher'],
  ['enterprise_mentor', 'teacher'],
  ['企业导师', 'teacher'],
  ['student', 'student'],
  ['学生', 'student']
])

const ROLE_VISIBILITY = {
  academic: new Set(['academic', 'teacher']),
  'student-affairs': new Set(['student-affairs', 'teacher']),
  teacher: new Set(['teacher']),
  student: new Set(['student'])
}

const PRIORITY_HELP_IDS = [
  'doc-lifecycle',
  'doc-teaching-affairs-preparation',
  'doc-academic-full-flow',
  'doc-course-schedule-full-flow',
  'doc-internship-full-flow',
  'doc-graduation-full-flow',
  'doc-student-status'
]

function uniqueById(entries) {
  const seen = new Set()
  return entries.filter((entry) => {
    if (!entry?.item?.id || seen.has(entry.item.id)) return false
    seen.add(entry.item.id)
    return true
  })
}

function tokenizeRoles(value) {
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

  if (/超级|平台|学校.*管理员|系统.*管理员/.test(raw)) return 'school-admin'
  if (/教务|教学管理/.test(raw)) return 'academic'
  if (/学工|辅导员|班主任/.test(raw)) return 'student-affairs'
  if (/教师|导师|指导/.test(raw)) return 'teacher'
  if (/学生/.test(raw)) return 'student'
  return ''
}

export function resolveHelpRole(authRole, authLabel = '') {
  return normalizeHelpRole(authRole) || normalizeHelpRole(authLabel) || 'all'
}

function getRoleTokens(item) {
  return tokenizeRoles(item?.roles ?? item?.role)
}

export function isHelpVisibleForRole(item, selectedRole = 'all') {
  const role = normalizeHelpRole(selectedRole) || 'all'
  if (role === 'all' || role === 'school-admin') return true

  const tokens = getRoleTokens(item)
  if (!tokens.length) return true

  const normalized = tokens.map(normalizeHelpRole).filter(Boolean)
  // 旧任务卡中有自由文本角色。无法识别时采用宽松显示，避免误隐藏；质量审计会单独标记。
  if (!normalized.length || normalized.includes('all')) return true

  const allowed = ROLE_VISIBILITY[role] || new Set([role])
  return normalized.some((candidate) => allowed.has(candidate))
}

function collectStrings(value, output = []) {
  if (typeof value === 'string') {
    output.push(value)
  } else if (Array.isArray(value)) {
    value.forEach((item) => collectStrings(item, output))
  } else if (value && typeof value === 'object') {
    Object.values(value).forEach((item) => collectStrings(item, output))
  }
  return output
}

function getSectionIndex() {
  const index = new Map()
  HELP_SECTIONS.forEach((section) => {
    section.items.forEach((item) => {
      if (!index.has(item.id)) {
        index.set(item.id, { key: section.key, label: section.label })
      }
    })
  })
  return index
}

const SECTION_INDEX = getSectionIndex()

function normalizeEntry(type, item) {
  const section = SECTION_INDEX.get(item.id) || { key: 'other', label: '其他帮助' }
  const roleTokens = getRoleTokens(item)
  const recognizedRoleTokens = roleTokens.map(normalizeHelpRole).filter(Boolean)
  const category = item.module || item.category || section.label || TYPE_LABELS[type]
  const missing = []
  if (!item.title) missing.push('title')
  if (!item.summary) missing.push('summary')
  if (!(item.keywords || []).length) missing.push('keywords')
  if (!roleTokens.length && type === 'card') missing.push('roles')
  if (roleTokens.length && !recognizedRoleTokens.length) missing.push('recognized-role')

  return {
    id: item.id,
    type,
    typeLabel: TYPE_LABELS[type],
    item,
    title: item.title,
    summary: item.summary || '',
    category,
    sectionKey: section.key,
    sectionLabel: section.label,
    roleTokens,
    recognizedRoleTokens,
    searchText: collectStrings({
      title: item.title,
      summary: item.summary,
      keywords: item.keywords,
      roles: item.roles || item.role,
      module: item.module,
      category: item.category,
      entry: item.entry,
      steps: item.steps,
      points: item.points,
      tips: item.tips,
      warnings: item.warnings,
      fields: item.fields,
      faq: item.faq,
      sections: item.sections
    }).join(' ').toLowerCase(),
    quality: {
      missing,
      isComplete: missing.length === 0
    }
  }
}

export const ALL_HELP_ENTRIES = uniqueById([
  ...HELP_CARDS.map((item) => normalizeEntry('card', item)),
  ...HELP_DOCS.map((item) => normalizeEntry('doc', item)),
  ...HELP_FLOWS.map((item) => normalizeEntry('flow', item))
])

const ENTRY_MAP = new Map(ALL_HELP_ENTRIES.map((entry) => [entry.id, entry]))

export function getHelpEntry(id) {
  if (!id) return null
  return ENTRY_MAP.get(id) || null
}

export function getRawHelpEntry(id) {
  return getHelpById(id)
}

export function getHelpCategories(role = 'all') {
  const counts = new Map()
  ALL_HELP_ENTRIES
    .filter((entry) => isHelpVisibleForRole(entry.item, role))
    .forEach((entry) => counts.set(entry.category, (counts.get(entry.category) || 0) + 1))
  return [...counts.entries()]
    .map(([value, count]) => ({ value, label: value, count }))
    .sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'))
}

export function searchHelpCenter(query, options = {}) {
  const q = String(query || '').trim().toLowerCase()
  const role = options.role || 'all'
  const category = options.category || 'all'
  const sectionKey = options.sectionKey || 'all'
  const limit = Number.isFinite(options.limit) ? options.limit : 100

  return ALL_HELP_ENTRIES
    .filter((entry) => isHelpVisibleForRole(entry.item, role))
    .filter((entry) => category === 'all' || entry.category === category)
    .filter((entry) => sectionKey === 'all' || entry.sectionKey === sectionKey)
    .filter((entry) => !q || entry.searchText.includes(q))
    .slice(0, limit)
}

export function getPriorityHelp(role = 'all', limit = 8) {
  const preferred = PRIORITY_HELP_IDS
    .map(getHelpEntry)
    .filter(Boolean)
    .filter((entry) => isHelpVisibleForRole(entry.item, role))

  const fallback = ALL_HELP_ENTRIES.filter(
    (entry) => !preferred.some((candidate) => candidate.id === entry.id) &&
      isHelpVisibleForRole(entry.item, role)
  )

  return [...preferred, ...fallback].slice(0, limit)
}

export function getHelpOverview(role = 'all') {
  const visible = ALL_HELP_ENTRIES.filter((entry) => isHelpVisibleForRole(entry.item, role))
  return {
    total: visible.length,
    taskCards: visible.filter((entry) => entry.type === 'card').length,
    flowGuides: visible.filter((entry) => entry.type === 'flow').length,
    visualGuides: visible.filter((entry) => Boolean(entry.item.embed)).length,
    qualityGaps: visible.filter((entry) => !entry.quality.isComplete).length
  }
}

export function getHelpSections(role = 'all', query = '', category = 'all') {
  const matchingIds = new Set(searchHelpCenter(query, { role, category }).map((entry) => entry.id))
  const seen = new Set()
  return HELP_SECTIONS
    .map((section) => ({
      key: section.key,
      label: section.label,
      items: section.items
        .map((item) => getHelpEntry(item.id))
        .filter(Boolean)
        .filter((entry) => matchingIds.has(entry.id))
        .filter((entry) => {
          if (seen.has(entry.id)) return false
          seen.add(entry.id)
          return true
        })
    }))
    .filter((section) => section.items.length)
}
