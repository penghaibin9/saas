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

const PRIORITY_HELP_IDS = [
  'sys-card-staff-account-role',
  'sys-card-role-permission-scope',
  'sys-card-org-foundation',
  'sys-card-student-import',
  'sys-card-access-diagnosis',
  'doc-lifecycle',
  'doc-teaching-affairs-preparation',
  'doc-academic-full-flow',
  'doc-course-schedule-full-flow',
  'doc-internship-full-flow',
  'doc-graduation-full-flow',
  'doc-student-status'
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

function normalizeEntry(type, item) {
  const section = SECTION_INDEX.get(item.id) || { key: 'other', label: '其他帮助' }
  const roleTokens = getHelpRoleTokens(item)
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
    searchText: buildHelpSearchText(item),
    quality: {
      missing,
      isComplete: missing.length === 0
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
