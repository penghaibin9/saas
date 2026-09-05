import { NAV_PLAN, matchPermission, searchNavPlan } from './navPlan.js'

const STUDENT_AFFAIRS_GROUP = 'student-affairs'
const COMPATIBILITY_ONLY_PATHS = new Set([
  '/admin/campus-service/grants'
])

const ENTRY_TYPE_LABELS = Object.freeze({
  ACTION: '动作',
  ARCHIVE: '归档',
  ANALYTICS_VIEW: '统计',
  CAPABILITY_ONLY: '能力',
  CONFIG_VIEW: '配置',
  LEDGER: '台账',
  TASK_QUEUE: '队列',
  WORKBENCH: '工作台'
})

function leafKey(leaf) {
  return `${leaf.label || ''}|${leaf.path || ''}`
}

function hasPermission(leaf, permissionPatterns) {
  if (!Array.isArray(permissionPatterns) || !permissionPatterns.length) return false
  if (leaf.permissionKey && !matchPermission(permissionPatterns, leaf.permissionKey)) return false
  if (Array.isArray(leaf.permissionAny) && leaf.permissionAny.length &&
      !leaf.permissionAny.some((code) => matchPermission(permissionPatterns, code))) {
    return false
  }
  if (Array.isArray(leaf.permissionAll) && leaf.permissionAll.length &&
      !leaf.permissionAll.every((code) => matchPermission(permissionPatterns, code))) {
    return false
  }
  return true
}

function isSearchableDeepLink(leaf) {
  return !!(
    leaf &&
    leaf.hidden &&
    leaf.searchable &&
    leaf.path &&
    leaf.entryType !== 'COMPAT' &&
    !COMPATIBILITY_ONLY_PATHS.has(leaf.path)
  )
}

function contextualLeaf(leaf) {
  return {
    ...leaf,
    hidden: false,
    contextualDeepLink: true,
    badge: ENTRY_TYPE_LABELS[leaf.entryType] || '更多',
    description: [leaf.sectionLabel, '当前工作区扩展三级页'].filter(Boolean).join(' · ')
  }
}

function rawStudentAffairsGroup() {
  return NAV_PLAN.find((item) => item.key === STUDENT_AFFAIRS_GROUP) || null
}

let searchableDeepLinkIndex = null
function getSearchableDeepLinkIndex() {
  if (searchableDeepLinkIndex) return searchableDeepLinkIndex
  const index = new Map()
  const rawGroup = rawStudentAffairsGroup()
  for (const rawMod of rawGroup?.children || []) {
    for (const rawLeaf of rawMod.children || []) {
      if (!isSearchableDeepLink(rawLeaf)) continue
      index.set(rawLeaf.path, { leaf: rawLeaf, mod: rawMod })
    }
  }
  searchableDeepLinkIndex = index
  return index
}

/**
 * 将 navPlan 中 D() 登记的真实低频页面，仅投影到当前展开工作区的三级区域。
 *
 * getVisibleNavPlan 继续保持普通侧栏的高频精简；这里不暴露 H() 对象详情、兼容路由，
 * 也不扩大权限。返回新对象，绝不修改 NAV_PLAN 或其缓存结果。
 */
export function projectStudentAffairsWorkspaceDeepLinks(group, permissionPatterns) {
  if (!group || group.key !== STUDENT_AFFAIRS_GROUP) return group
  if (!Array.isArray(permissionPatterns) || !permissionPatterns.length) return group
  const rawGroup = rawStudentAffairsGroup()
  if (!rawGroup) return group
  const rawMods = new Map(rawGroup.children.map((item) => [item.key, item]))

  return {
    ...group,
    children: group.children.map((visibleMod) => {
      const rawMod = rawMods.get(visibleMod.key)
      if (!rawMod) return visibleMod
      const visibleByKey = new Map((visibleMod.children || []).map((leaf) => [leafKey(leaf), leaf]))
      const merged = []

      for (const rawLeaf of rawMod.children || []) {
        const existing = visibleByKey.get(leafKey(rawLeaf))
        if (existing) {
          merged.push(existing)
          continue
        }
        if (!isSearchableDeepLink(rawLeaf)) continue
        if (!hasPermission(rawLeaf, permissionPatterns)) continue
        merged.push(contextualLeaf(rawLeaf))
      }

      return { ...visibleMod, children: merged }
    })
  }
}

/**
 * 将公共 searchNavPlan 的同一权威搜索结果，适配为学工低频 D() 页的短标题结果。
 * 不再自行扫描、匹配或排序查询文本；权限、缓存与搜索顺序均由 navPlan 统一负责。
 */
export function searchStudentAffairsWorkspaceDeepLinks(query, permissionPatterns) {
  const q = String(query || '').trim()
  if (!q || !Array.isArray(permissionPatterns) || !permissionPatterns.length) return []
  const index = getSearchableDeepLinkIndex()

  return searchNavPlan(q, permissionPatterns)
    .map((result) => {
      const source = index.get(result.path)
      if (!source || !hasPermission(source.leaf, permissionPatterns)) return null
      return {
        groupKey: STUDENT_AFFAIRS_GROUP,
        label: source.leaf.label,
        path: source.leaf.path,
        badge: ENTRY_TYPE_LABELS[source.leaf.entryType] || '',
        sub: [source.mod.label, source.leaf.sectionLabel].filter(Boolean).join(' · ')
      }
    })
    .filter(Boolean)
    .slice(0, 16)
}

export function countContextualWorkspaceDeepLinks(group) {
  if (!group) return 0
  return group.children.reduce(
    (total, item) => total + (item.children || []).filter((leaf) => leaf.contextualDeepLink).length,
    0
  )
}
