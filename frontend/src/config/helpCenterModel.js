import {
  HELP_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  HELP_SECTIONS,
  getHelpById
} from './helpCenterRuntime'
import {
  HELP_ROLE_OPTIONS,
  buildHelpSearchText,
  getHelpRoleTokens,
  isHelpVisibleForRole,
  normalizeHelpRole,
  resolveHelpRole,
  uniqueHelpEntries
} from './helpCenterCore'

export { HELP_ROLE_OPTIONS, isHelpVisibleForRole, normalizeHelpRole, resolveHelpRole }

const TYPE_LABELS = {
  card: '帮助任务卡',
  doc: '功能帮助',
  flow: '业务流程图'
}

/**
 * V2 首页优先级只放已经进入运行时发布白名单的高频任务或已核验流程。
 * 未重新验真的百科/旧流程不再靠“历史优先级”被顶到首页。
 */
const PRIORITY_HELP_IDS = [
  'sys-card-first-school-setup',
  'auth-card-staff-login-password',
  'sys-card-staff-account-role',
  'sys-card-role-permission-scope',
  'sys-card-org-foundation',
  'sys-card-student-import',
  'sys-card-access-diagnosis',
  'student-card-single-create',
  'student-card-list-filter',
  'student-card-secure-export',
  'aa-card-term-setup',
  'aa-card-status-change',
  'aa-card-grade-entry',
  'aa-card-grade-review-publish',
  'aa-card-grade-change',
  'aa-card-selection-round',
  'aa-card-selection-publish',
  'aa-card-exam-arrangement',
  'aa-card-exam-publish',
  'in-card-batch-rules',
  'in-card-eval-score',
  'gd-card-defense-grade',
  'sa-card-risk-handle',
  'sa-card-archive',
  'flow-leave',
  'flow-in-score',
  'mobile-student-internship-checkin',
  'mobile-student-internship-weekly',
  'mobile-student-graduation-topic',
  'mobile-student-orientation-collect',
  'mobile-student-affairs-leave',
  'mobile-student-academic-selection',
  'mobile-teacher-todos',
  'mobile-teacher-internship-process',
  'mobile-teacher-graduation-topic-review',
  'mobile-teacher-grade-entry'
]

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

function hasList(item, field) {
  return Array.isArray(item?.[field]) && item[field].filter(Boolean).length > 0
}

function hasEntryLocation(item) {
  return Boolean(item?.entry || item?.route || item?.mobilePath)
}

function hasPermissionGuidance(item) {
  if (hasList(item, 'permissions') || hasList(item, 'permissionNotes')) return true
  const evidence = [
    ...(item?.prerequisites || []),
    ...(item?.warnings || []),
    ...(item?.troubleshooting || [])
  ].map((value) => String(value)).join(' ')
  return /权限|授权|数据范围|allowedactions|角色|管理员|本人授课范围/i.test(evidence)
}

/**
 * V2 正式任务卡的七维知识合同：
 * 1. 适用角色 roles
 * 2. 入口位置 entry / route / mobilePath
 * 3. 操作步骤 steps
 * 4. 前置条件 prerequisites
 * 5. 成功结果 successCriteria
 * 6. 异常处理 troubleshooting
 * 7. 权限说明 permissions / permissionNotes，或正文中明确的权限/数据范围/allowedActions 证据
 *
 * 运行时发布资格由 helpCenterRuntime 的 verified-only 白名单控制；这里负责把“已核验但结构尚未
 * 收口”的内容明确记为 quality gap，禁止再用只有 title/summary/keywords 的低门槛冒充成熟帮助。
 */
function getQualityMissing(type, item, roleTokens, recognizedRoleTokens) {
  const missing = []
  if (!item.title) missing.push('title')
  if (!item.summary) missing.push('summary')
  if (!(item.keywords || []).length) missing.push('keywords')

  if (type === 'card') {
    if (!roleTokens.length) missing.push('roles')
    if (roleTokens.length && !recognizedRoleTokens.length) missing.push('recognized-role')
    if (!hasEntryLocation(item)) missing.push('entry-location')
    if (!hasList(item, 'steps')) missing.push('steps')
    if (!hasList(item, 'prerequisites')) missing.push('prerequisites')
    if (!hasList(item, 'successCriteria')) missing.push('success-criteria')
    if (!hasList(item, 'troubleshooting')) missing.push('troubleshooting')
    if (!hasPermissionGuidance(item)) missing.push('permission-guidance')
  }

  if (type === 'flow' && !hasList(item, 'steps')) missing.push('steps')
  return missing
}

function normalizeEntry(type, item) {
  const section = SECTION_INDEX.get(item.id) || { key: 'other', label: '其他帮助' }
  const roleTokens = getHelpRoleTokens(item)
  const recognizedRoleTokens = roleTokens.map(normalizeHelpRole).filter(Boolean)
  const category = item.module || item.category || section.label || TYPE_LABELS[type]
  const missing = getQualityMissing(type, item, roleTokens, recognizedRoleTokens)

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
    searchText: buildHelpSearchText(item),
    quality: {
      missing,
      isComplete: missing.length === 0,
      contract: type === 'card' ? 'knowledge-cleaning-v2-seven-dimensions' : 'verified-reference'
    }
  }
}

export const ALL_HELP_ENTRIES = uniqueHelpEntries([
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
