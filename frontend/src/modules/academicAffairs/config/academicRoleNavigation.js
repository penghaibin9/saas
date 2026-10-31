// 岗位导航上限与当前发布权限取交集；后端仍独立校验权限、范围和业务状态。
import contract from '../../../../../shared/contracts/role-menus/academic.json' with { type: 'json' }
import { NAV_PLAN, matchPermission } from '../../../config/navPlan.js'
import { coreGroupEntitled } from '../../../security/moduleEntitlement.js'

const ROOT = '/admin/academic-affairs'
const leaves = new Map(NAV_PLAN.find(group => group.key === 'academic-affairs').children
  .flatMap(module => module.children || []).map(leaf => [leaf.leafId, leaf]))

function roleCode(ctx) {
  return String(ctx?.currentRole?.roleCode || ctx?.currentRole?.roleType || ctx?.currentRoleCode || '').toUpperCase()
}
export function hasAcademicRoleMenu(ctx) { return Boolean(contract.roles[roleCode(ctx)]) }

function permitted(leaf, ctx) {
  const patterns = ctx?.permissionPatterns || []
  const any = leaf.permissionAny || [], all = leaf.permissionAll || []
  return Boolean(leaf.permissionKey || any.length || all.length)
    && (!leaf.permissionKey || matchPermission(patterns, leaf.permissionKey))
    && (!any.length || any.some(key => matchPermission(patterns, key)))
    && all.every(key => matchPermission(patterns, key))
}

export function academicRoleModules(ctx) {
  const policy = contract.roles[roleCode(ctx)]
  if (!policy || !coreGroupEntitled('academic-affairs', ctx?.moduleEntitlements, ctx?.moduleAccessHealthy !== false)) return []
  return policy.groups.map(group => {
    const children = group.entries.flatMap(spec => {
      const source = leaves.get(spec.leafId)
      if (!source || source.hidden || source.disabled || source.status === 'planned') return []
      const leaf = { ...source, ...spec, menuSecondary: false,
        ...(spec.permissionKey ? { permissionAny: [], permissionAll: [], menuRequiresAny: [] } : {}) }
      return permitted(leaf, ctx) ? [leaf] : []
    })
    return { key: group.key, label: group.label, children, path: children[0]?.path || '',
      status: 'implemented', disabled: false, entryType: 'CONTAINER' }
  }).filter(group => group.children.length)
}

function refUrl(ref) {
  try {
    const path = typeof ref === 'string' ? ref : ref?.path
    if (!path || /\\|%2f|%5c/i.test(path)) return null
    const url = new URL(path, 'https://role-menu.invalid')
    if (url.origin !== 'https://role-menu.invalid') return null
    if (typeof ref === 'object') for (const [key, raw] of Object.entries(ref.query || {})) {
      url.searchParams.delete(key)
      for (const value of (Array.isArray(raw) ? raw : [raw])) if (value !== undefined) url.searchParams.append(key, value ?? '')
    }
    return url
  } catch { return null }
}

function matches(rule, target) {
  const expected = refUrl(rule.path)
  if (!expected) return false
  const expression = expected.pathname.replace(/\/$/, '').split('/').map(part =>
    part === ':id' ? '[1-9][0-9]*' : part === ':key' ? '[^/]+' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('/')
  if (!new RegExp(`^${expression}$`).test(target.pathname.replace(/\/$/, ''))) return false
  const query = { ...Object.fromEntries(expected.searchParams), ...(rule.query || {}) }
  for (const [key, value] of Object.entries(query)) if (target.searchParams.get(key) !== value) return false
  // 页签/动作决定页面身份；筛选、分页和业务对象编号不替代身份。
  return contract.selectorKeys.every(key => !target.searchParams.has(key)
    || (target.searchParams.getAll(key).length === 1 && target.searchParams.get(key) === query[key]))
}

export function academicRoleAllows(ref, ctx) {
  const policy = contract.roles[roleCode(ctx)]
  if (!policy) return true
  const target = refUrl(ref)
  if (!target) return false
  if (!/^\/admin\/(academic-affairs|academic)(?:\/|$)/.test(target.pathname)) return true
  if (!coreGroupEntitled('academic-affairs', ctx?.moduleEntitlements, ctx?.moduleAccessHealthy !== false)) return false
  const menuLeaves = academicRoleModules(ctx).flatMap(group => group.children)
  const allowed = [...menuLeaves, ...policy.routes.filter(rule => permitted(rule, ctx))]
  if (!allowed.some(rule => matches(rule, target))) return false
  if (target.searchParams.has('_workspace')) {
    if (target.searchParams.getAll('_workspace').length !== 1) return false
    const identity = target.searchParams.get('_workspace')
    if (!menuLeaves.some(leaf => {
      if (![leaf.leafId, ...(leaf.legacyWorkspaceIds || [])].includes(identity)) return false
      const owner = refUrl(leaf.path)
      const pathMatches = target.pathname === owner.pathname
        || (owner.pathname !== ROOT && target.pathname.startsWith(owner.pathname + '/'))
      return pathMatches && [...owner.searchParams].every(([key, value]) => target.searchParams.get(key) === value)
    })) return false
  }
  return true
}

export function academicRoleDefaultPath(ctx) { return academicRoleModules(ctx)[0]?.path || '' }

export function filterAcademicRoleLinks(items, ctx) {
  if (!hasAcademicRoleMenu(ctx)) return items || []
  return (items || []).filter(item => !(item.to || item.path) || academicRoleAllows(item.to || item.path, ctx))
}

export function academicRoleSearchResults(items, ctx) {
  if (!hasAcademicRoleMenu(ctx)) return items || []
  const labels = new Map(academicRoleModules(ctx).flatMap(group => group.children.map(leaf =>
    [leaf.path, `${group.label} / ${leaf.label}`])))
  const seen = new Set()
  return filterAcademicRoleLinks(items, ctx).map(item => labels.has(item.to)
    ? { ...item, label: labels.get(item.to) } : item).filter(item => {
    const key = item.to ? `${item.kind}|${item.to}` : `${item.kind}|${item.label}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function academicRoleTabs(tabs, path, ctx, queryKey = 'tab') {
  if (!hasAcademicRoleMenu(ctx)) return tabs
  return tabs.filter(tab => academicRoleAllows({ path, query: { [queryKey]: tab.key } }, ctx))
}

export function academicRoleActiveModule(ctx, ref) {
  const target = refUrl(ref)
  if (!target) return ''
  let best = { key: '', score: -1 }
  for (const group of academicRoleModules(ctx)) for (const leaf of group.children) {
    const candidate = refUrl(leaf.path)
    if (!(target.pathname === candidate.pathname || target.pathname.startsWith(candidate.pathname + '/'))) continue
    if (![...candidate.searchParams].every(([key, value]) => target.searchParams.get(key) === value)) continue
    const score = candidate.pathname.length + candidate.searchParams.size * 1000
    if (score > best.score) best = { key: group.key, score }
  }
  return best.key
}
