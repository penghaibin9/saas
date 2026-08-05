/**
 * 管理端一级图标轨菜单（PC-10-MODULE-INTEGRATION-FINAL-RUN）。
 *
 * 与 navPlan.js 同源：一级分组 + 二级入口从 NAV_PLAN / PLATFORM_PLAN 投影生成，
 * 侧栏完整二/三级仍由 BasePortalLayout 直接消费 getVisibleNavPlan。
 * 本文件只提供轨数据 + 权限过滤，不另维护一套业务叶子。
 */
import { matchPermission, NAV_PLAN, PLATFORM_PLAN } from '@/config/navPlan'

/** 角色类型（与后端 role.roleType 对齐；用于跨模块可见性判断，非角色名硬编码） */
export const ROLE_TYPE = {
  PLATFORM: 'PLATFORM',
  SCHOOL_ADMIN: 'SCHOOL_ADMIN',
  ACADEMIC_STAFF: 'ACADEMIC_STAFF',
  COUNSELOR: 'COUNSELOR',
  AUDITOR: 'AUDITOR',
  STUDENT: 'STUDENT'
}

const GROUP_ICON = {
  workbench: '◫',
  'student-affairs': '☰',
  'academic-affairs': '◈',
  graduation: '✿',
  internship: '✎',
  system: '⚙',
  platform: '☁'
}

function inferModuleCode(groupKey, path) {
  const p = String(path || '')
  if (p.startsWith('/admin/orientation')) return 'ORIENTATION'
  if (p.startsWith('/admin/campus-service')) return 'CAMPUS_SERVICE'
  if (p.startsWith('/admin/data-center')) return 'DATA_CENTER'
  if (p.startsWith('/admin/approval')) return 'APPROVAL'
  if (p.startsWith('/admin/employment')) return 'EMPLOYMENT'
  if (p.startsWith('/admin/workflow')) return 'WORKFLOW'
  if (p.startsWith('/admin/platform')) return 'PLATFORM'
  if (p === '/workbench' || p.startsWith('/admin/messages') || p.startsWith('/admin/help')) return 'WORKBENCH'
  const map = {
    workbench: 'WORKBENCH',
    'student-affairs': 'STUDENT',
    'academic-affairs': 'ACADEMIC',
    graduation: 'GRADUATION',
    internship: 'INTERNSHIP',
    system: 'SYSTEM',
    platform: 'PLATFORM'
  }
  return map[groupKey] || 'WORKBENCH'
}

function firstLeafPermission(mod) {
  if (mod.permissionKey) return mod.permissionKey
  const leaf = (mod.children || []).find((c) => c.permissionKey && c.path && !c.disabled && !c.hidden)
  return leaf ? leaf.permissionKey : undefined
}

function resolveModPath(mod) {
  if (mod.path) return mod.path
  const leaf = (mod.children || []).find((c) => c.path && !c.disabled && !c.hidden)
  return leaf ? leaf.path : ''
}

/** 从 navPlan 投影一级轨菜单树（含平台组） */
function buildAdminMenuFromNavPlan() {
  const groups = [...NAV_PLAN, PLATFORM_PLAN]
  return groups.map((group) => {
    const children = (group.children || [])
      .map((mod) => {
        const path = resolveModPath(mod)
        if (!path) return null
        const permissionKey = firstLeafPermission(mod)
        const leaf = {
          key: mod.key,
          label: mod.label,
          path,
          moduleCode: inferModuleCode(group.key, path),
          ...(permissionKey ? { permissionKey } : {})
        }
        if (group.platformOnly || group.key === 'platform') leaf.platformOnly = true
        if (path.includes('/logs') || path.includes('/security')) leaf.sensitive = true
        return leaf
      })
      .filter(Boolean)
    return {
      key: group.key,
      label: group.label,
      icon: GROUP_ICON[group.key] || '•',
      ...(group.platformOnly || group.key === 'platform' ? { platformOnly: true } : {}),
      children
    }
  }).filter((g) => g.children.length > 0)
}

/**
 * 一级 / 二级菜单树 —— 运行时由 NAV_PLAN 投影，禁止再手写第二份业务目录。
 */
export const ADMIN_MENU = buildAdminMenuFromNavPlan()

/** 角色类型 → 可见模块 moduleCode 白名单（仅非生产降级；正式环境缺权限上下文时 fail-closed） */
const ROLE_MODULE_ALLOW = {
  [ROLE_TYPE.PLATFORM]: ['PLATFORM'],
  [ROLE_TYPE.SCHOOL_ADMIN]: ['WORKBENCH', 'WORKFLOW', 'STUDENT', 'ORIENTATION', 'CAMPUS_SERVICE', 'ACADEMIC', 'INTERNSHIP', 'GRADUATION', 'EMPLOYMENT', 'DATA_CENTER', 'APPROVAL', 'SYSTEM'],
  [ROLE_TYPE.ACADEMIC_STAFF]: ['WORKBENCH', 'STUDENT', 'ACADEMIC', 'DATA_CENTER', 'APPROVAL', 'INTERNSHIP', 'GRADUATION', 'EMPLOYMENT'],
  [ROLE_TYPE.COUNSELOR]: ['WORKBENCH', 'STUDENT', 'ORIENTATION', 'CAMPUS_SERVICE', 'ACADEMIC', 'INTERNSHIP'],
  [ROLE_TYPE.AUDITOR]: ['WORKBENCH', 'SYSTEM', 'DATA_CENTER', 'APPROVAL'],
  [ROLE_TYPE.STUDENT]: ['WORKBENCH']
}

function roleType(ctx) {
  return (ctx && ctx.currentRole && (
    ctx.currentRole.roleType || ctx.currentRole.type || ctx.currentRole.roleCode
  )) || null
}

function workbenchOnly(leaf) {
  return !leaf.platformOnly && !leaf.sensitive && leaf.moduleCode === 'WORKBENCH'
}

/**
 * 某叶子节点是否有权限。
 * - 有权限集：严格按 permissionKey 命中；无 permissionKey 的公共工作台入口保留。
 * - 正式环境缺权限集：fail-closed，只保留工作台，禁止按粗角色放大菜单。
 * - 开发/测试环境：允许角色白名单降级，便于本地排障，但后端仍是最终权限边界。
 */
function canSeeLeaf(leaf, ctx) {
  const rt = roleType(ctx)
  if (leaf.platformOnly && rt !== ROLE_TYPE.PLATFORM) return false
  if (rt === ROLE_TYPE.PLATFORM && leaf.moduleCode !== 'PLATFORM') return false
  if (leaf.sensitive && rt === ROLE_TYPE.COUNSELOR) return false

  const patterns = ctx && ctx.permissionPatterns
  if (Array.isArray(patterns)) {
    if (leaf.permissionKey) return matchPermission(patterns, leaf.permissionKey)
    return workbenchOnly(leaf)
  }

  if (import.meta.env && import.meta.env.PROD) return workbenchOnly(leaf)
  if (rt) return (ROLE_MODULE_ALLOW[rt] || ['WORKBENCH']).includes(leaf.moduleCode)
  return workbenchOnly(leaf)
}

function contextSignature(ctx) {
  const role = (ctx && ctx.currentRole) || {}
  const patterns = Array.isArray(ctx && ctx.permissionPatterns)
    ? [...ctx.permissionPatterns].sort().join(',')
    : '__missing_permissions__'
  return [
    (ctx && (ctx.tenantId || ctx.tenant_id)) || (ctx && ctx.tenantBrandConfig && ctx.tenantBrandConfig.tenantId) || '',
    (ctx && (ctx.userId || ctx.user_id)) || role.userId || '',
    (ctx && (ctx.activeContextId || ctx.contextId)) || role.contextId || '',
    roleType(ctx) || '__missing_role__',
    (ctx && ctx.permissionVersion) || '',
    (ctx && ctx.ctxKey) || '',
    patterns
  ].join('|')
}

const _adminMenuVisibleCache = new Map()

export function clearVisibleAdminMenuCache() {
  _adminMenuVisibleCache.clear()
}

export function getVisibleAdminMenu(ctx) {
  const rt = roleType(ctx) || '__default__'
  const cacheKey = contextSignature(ctx)
  if (_adminMenuVisibleCache.has(cacheKey)) return _adminMenuVisibleCache.get(cacheKey)
  const result = ADMIN_MENU
    .filter((group) => {
      if (group.platformOnly && rt !== ROLE_TYPE.PLATFORM) return false
      return true
    })
    .map((group) => ({ ...group, children: group.children.filter((leaf) => canSeeLeaf(leaf, ctx)) }))
    .filter((group) => group.children.length > 0)
  if (_adminMenuVisibleCache.size > 64) _adminMenuVisibleCache.clear()
  _adminMenuVisibleCache.set(cacheKey, result)
  return result
}

/** 依据当前路径定位激活的一级/二级 key（供壳高亮使用） */
export function findActiveMenu(path) {
  for (const group of ADMIN_MENU) {
    const leaf = [...group.children]
      .sort((a, b) => b.path.length - a.path.length)
      .find((l) => path === l.path || path.startsWith(l.path + '/') || (l.path.includes('?') && path === l.path.split('?')[0]))
    if (leaf) return { groupKey: group.key, leafKey: leaf.key }
  }
  return { groupKey: '', leafKey: '' }
}

export const LEGACY_GROUP_KEY_MAP = {
  'student-center': 'student-affairs',
  practice: 'graduation',
  'data-center': 'workbench',
  'wf-center': 'system'
}

export const SEARCH_ALIASES = [
  { keywords: ['工作台', '我的工作台', '首页'], path: '/workbench', label: '工作台 / 我的工作台' },
  { keywords: ['学生中心', '学工中心', '学生画像', '学生主档'], path: '/admin/student', label: '学工中心 / 学生画像' },
  { keywords: ['数字迎新', '迎新', '新生报到'], path: '/admin/orientation', label: '学工中心 / 数字迎新' },
  { keywords: ['在校服务', '请假', '奖助', '宿舍', '违纪'], path: '/admin/campus-service', label: '学工中心 / 在校服务' },
  { keywords: ['学业过程', '教务中心', '成绩', '课程', '学业预警'], path: '/admin/academic', label: '教务中心 / 学业过程' },
  { keywords: ['教学实践', '毕业设计', '毕设', '选题', '答辩'], path: '/admin/graduation', label: '毕业设计中心' },
  { keywords: ['岗位实习', '实习', '打卡', '周报', '实习工作台', '今日工作'], path: '/admin/internship', label: '岗位实习中心 / 今日工作' },
  { keywords: ['就业服务', '就业', '未就业帮扶', '就业转化'], path: '/admin/employment', label: '就业服务（就业中心）' },
  { keywords: ['数据中心', '数据驾驶舱', '领导驾驶舱', '生命周期'], path: '/admin/data-center', label: '工作台 / 领导驾驶舱' },
  { keywords: ['审批中心', '我的待办', '待办', '已办'], path: '/admin/approval', label: '工作台 / 审批中心' },
  { keywords: ['消息中心', '我的消息', '站内信'], path: '/admin/messages/inbox', label: '工作台 / 消息中心' },
  { keywords: ['权限与流程', '流程配置', '审批模板', '角色', '权限'], path: '/admin/workflow', label: '系统管理 / 权限与流程' },
  { keywords: ['系统管理', '用户', '菜单', '数据范围', '品牌'], path: '/admin/system', label: '系统管理' },
  { keywords: ['安全审计', '日志', '安全与审计'], path: '/admin/system/logs', label: '系统管理 / 安全与审计' }
]

const ALIAS_SEARCH_INDEX = SEARCH_ALIASES.map((a) => ({
  label: a.label,
  path: a.path,
  keywords: a.keywords || [],
  labelLower: a.label.toLowerCase(),
  keywordsLower: (a.keywords || []).map((k) => k.toLowerCase())
}))

const _aliasSearchCache = new Map()

function aliasMatchesEntry(entry, q) {
  if (entry.labelLower.includes(q)) return true
  return entry.keywordsLower.some((kk) => kk.includes(q) || q.includes(kk))
}

export function searchSearchAliases(query, { scopeGroupKeys = null, emptyLimit = 4 } = {}) {
  const q = (query || '').trim().toLowerCase()
  const scopeKey = scopeGroupKeys ? [...scopeGroupKeys].sort().join(',') : '*'
  const cacheKey = `${q}|${scopeKey}|${emptyLimit}`
  if (_aliasSearchCache.has(cacheKey)) return _aliasSearchCache.get(cacheKey)
  const inScope = (entry) => {
    if (!scopeGroupKeys) return true
    const gk = findActiveMenu(entry.path).groupKey
    return !gk || scopeGroupKeys.has(gk)
  }
  let matched
  if (!q) {
    matched = ALIAS_SEARCH_INDEX.filter(inScope).slice(0, emptyLimit)
  } else {
    matched = []
    for (const entry of ALIAS_SEARCH_INDEX) {
      if (!inScope(entry)) continue
      if (aliasMatchesEntry(entry, q)) matched.push(entry)
      if (matched.length >= 20) break
    }
  }
  const result = matched.map((e) => ({ label: e.label, path: e.path }))
  if (_aliasSearchCache.size > 64) _aliasSearchCache.clear()
  _aliasSearchCache.set(cacheKey, result)
  return result
}

export default ADMIN_MENU
