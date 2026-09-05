import { NAV_PLAN, matchPermission } from './navPlan.js'

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
  if (!Array.isArray(permissionPatterns)) return true
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

/**
 * 将 navPlan 中 D() 登记的真实低频页面，仅投影到当前展开工作区的三级区域。
 *
 * getVisibleNavPlan 继续保持普通侧栏的高频精简；这里不暴露 H() 对象详情、兼容路由，
 * 也不扩大权限。返回新对象，绝不修改 NAV_PLAN 或其缓存结果。
 */
export function projectStudentAffairsWorkspaceDeepLinks(group, permissionPatterns) {
  if (!group || group.key !== STUDENT_AFFAIRS_GROUP) return group
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
 * 为学工门户的功能搜索补回 D() 深链。
 * 搜索严格按当前权限集过滤；权限上下文缺失时 fail-closed，且兼容重定向永不作为新入口暴露。
 */
export function searchStudentAffairsWorkspaceDeepLinks(query, permissionPatterns) {
  const q = String(query || '').trim().toLowerCase()
  if (!q || !Array.isArray(permissionPatterns)) return []
  const rawGroup = rawStudentAffairsGroup()
  if (!rawGroup) return []
  const results = []

  for (const rawMod of rawGroup.children || []) {
    for (const rawLeaf of rawMod.children || []) {
      if (!isSearchableDeepLink(rawLeaf)) continue
      if (!hasPermission(rawLeaf, permissionPatterns)) continue
      const searchText = [rawLeaf.label, rawLeaf.sectionLabel, rawLeaf.description, rawMod.label]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (!searchText.includes(q)) continue
      results.push({
        groupKey: STUDENT_AFFAIRS_GROUP,
        label: rawLeaf.label,
        path: rawLeaf.path,
        badge: ENTRY_TYPE_LABELS[rawLeaf.entryType] || '',
        sub: [rawMod.label, rawLeaf.sectionLabel].filter(Boolean).join(' · ')
      })
    }
  }

  return results.slice(0, 16)
}

export function countContextualWorkspaceDeepLinks(group) {
  if (!group) return 0
  return group.children.reduce(
    (total, item) => total + (item.children || []).filter((leaf) => leaf.contextualDeepLink).length,
    0
  )
}
