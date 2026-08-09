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
import {
  HELP_V3_CORE_JOURNEYS,
  HELP_V3_HOME_INTENTS,
  HELP_V3_QUICK_QUESTIONS
} from './help/helpCenterV3'

export {
  HELP_ROLE_OPTIONS,
  HELP_V3_HOME_INTENTS,
  HELP_V3_QUICK_QUESTIONS,
  isHelpVisibleForRole,
  normalizeHelpRole,
  resolveHelpRole
}

const TYPE_LABELS = {
  card: '帮助任务卡',
  doc: '功能帮助',
  flow: '业务流程图'
}

/**
 * V3 首页优先级只放已经进入运行时发布白名单的高频任务。
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
  'in-v2-student-application',
  'in-v2-teacher-process',
  'in-v2-enterprise-evaluation',
  'in-v2-score',
  'gd-v2-topic-selection',
  'gd-v2-proposal',
  'gd-v2-defense',
  'gd-v2-grade',
  'sa-card-risk-handle',
  'sa-card-archive',
  'mobile-unified-help-entry',
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
 * V3 在此基础上继续推进“下一步 / 退回异常 / 什么时候找管理员”等免培训字段；
 * 在 V3-08 质量闸门完成前，不用放宽 V2 七维合同，也不把尚未补齐 V3 字段的真实任务下线。
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

const HELP_QUERY_STOP_WORDS = new Set([
  '为什么', '什么', '怎么', '怎样', '如何', '请问', '我', '我的', '我要', '我想',
  '了', '呢', '吗', '啊', '呀', '吧', '不', '不了', '不能', '无法', '是否', '能否'
])

function normalizeHelpQuery(value) {
  const raw = String(value || '')
  try {
    return raw.normalize('NFKC').trim().toLowerCase()
  } catch {
    return raw.trim().toLowerCase()
  }
}

/**
 * 问题式搜索不能要求整句连续命中。
 * 优先使用 Intl.Segmenter 做中文/英文混合分词，过滤“为什么/怎么/不了”等问句噪声；
 * 这样“为什么成绩提交不了”会落到“成绩 + 提交”，“成绩 409”会落到“成绩 + 409”。
 */
export function tokenizeHelpQuery(query) {
  const normalized = normalizeHelpQuery(query)
  if (!normalized) return []

  let parts = []
  try {
    if (typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function') {
      const segmenter = new Intl.Segmenter('zh-CN', { granularity: 'word' })
      parts = [...segmenter.segment(normalized)]
        .filter((item) => item.isWordLike)
        .map((item) => item.segment)
    }
  } catch {
    parts = []
  }
  if (!parts.length) {
    const fallback = normalized
      .replace(/为什么|怎么办|怎么|怎样|如何|请问|不了|不能|无法|是否|能否/g, ' ')
      .split(/[^0-9a-z\u4e00-\u9fff_.:-]+/i)
    parts = fallback
  }

  return [...new Set(parts
    .map((part) => normalizeHelpQuery(part))
    .filter(Boolean)
    .filter((part) => !HELP_QUERY_STOP_WORDS.has(part)))]
}

export function matchesHelpSearchText(searchText, query) {
  const haystack = normalizeHelpQuery(searchText)
  const q = normalizeHelpQuery(query)
  if (!q) return true
  if (haystack.includes(q)) return true
  const tokens = tokenizeHelpQuery(q)
  if (!tokens.length) return false
  return tokens.every((token) => haystack.includes(token))
}

export function searchHelpCenter(query, options = {}) {
  const q = normalizeHelpQuery(query)
  const role = options.role || 'all'
  const category = options.category || 'all'
  const sectionKey = options.sectionKey || 'all'
  const limit = Number.isFinite(options.limit) ? options.limit : 100

  return ALL_HELP_ENTRIES
    .filter((entry) => isHelpVisibleForRole(entry.item, role))
    .filter((entry) => category === 'all' || entry.category === category)
    .filter((entry) => sectionKey === 'all' || entry.sectionKey === sectionKey)
    .filter((entry) => matchesHelpSearchText(entry.searchText, q))
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

/**
 * V3 首页核心业务地图。
 * 每个节点必须能解析到 verified-only 运行时中的真实帮助条目；不存在或当前角色不可见的节点不会展示。
 */
export function getV3CoreJourneys(role = 'all') {
  return HELP_V3_CORE_JOURNEYS
    .map((journey) => {
      const verifiedEntries = journey.helpIds.map(getHelpEntry).filter(Boolean)
      const entries = verifiedEntries.filter((entry) => isHelpVisibleForRole(entry.item, role))
      return {
        ...journey,
        entries,
        verifiedCount: verifiedEntries.length,
        visibleCount: entries.length
      }
    })
    .filter((journey) => journey.entries.length)
}

export function getV3HomeModel(role = 'all') {
  return {
    intents: HELP_V3_HOME_INTENTS,
    quickQuestions: HELP_V3_QUICK_QUESTIONS,
    priorityTasks: getPriorityHelp(role, 8),
    journeys: getV3CoreJourneys(role)
  }
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