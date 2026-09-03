import { NAV_PLAN, matchPermission } from './navPlan.js'

const STUDENT_AFFAIRS_GROUP = 'student-affairs'

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
  if (Array.isArray(leaf.permissionAny) && leaf.permissionAny.length) {
    return leaf.permissionAny.some((code) => matchPermission(permissionPatterns, code))
  }
  return true
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

/**
 * 将 navPlan 中 D() 登记的真实低频页面，仅投影到当前展开工作区的三级区域。
 *
 * getVisibleNavPlan 继续保持普通侧栏的高频精简；这里不暴露 H() 对象详情、兼容路由，
 * 也不扩大权限。返回新对象，绝不修改 NAV_PLAN 或其缓存结果。
 */
export function projectStudentAffairsWorkspaceDeepLinks(group, permissionPatterns) {
  if (!group || group.key !== STUDENT_AFFAIRS_GROUP) return group
  const rawGroup = NAV_PLAN.find((item) => item.key === STUDENT_AFFAIRS_GROUP)
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
        if (!rawLeaf.hidden || !rawLeaf.searchable || !rawLeaf.path) continue
        if (!hasPermission(rawLeaf, permissionPatterns)) continue
        merged.push(contextualLeaf(rawLeaf))
      }

      return { ...visibleMod, children: merged }
    })
  }
}

export function countContextualWorkspaceDeepLinks(group) {
  if (!group) return 0
  return group.children.reduce(
    (total, item) => total + (item.children || []).filter((leaf) => leaf.contextualDeepLink).length,
    0
  )
}
