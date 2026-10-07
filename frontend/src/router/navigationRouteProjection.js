function cleanPath(value) {
  const withoutQuery = String(value || '').split('?')[0]
  const normalized = `/${withoutQuery}`.replace(/\/{2,}/g, '/').replace(/\/$/, '')
  return normalized || '/'
}

function cleanPattern(value) {
  const normalized = `/${String(value || '')}`.replace(/\/{2,}/g, '/').replace(/\/$/, '')
  return normalized || '/'
}

function joinPattern(parent, child) {
  if (String(child || '').startsWith('/')) return cleanPattern(child)
  return cleanPattern(`${parent || ''}/${child || ''}`)
}

function routeMatches(pattern, actual) {
  const tokens = cleanPattern(pattern).split('/').filter(Boolean)
  let expression = '^'
  for (const token of tokens) {
    if (token.startsWith(':')) {
      expression += token.endsWith('?') ? '(?:/[^/]+)?' : '/[^/]+'
    } else {
      expression += `/${token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`
    }
  }
  return new RegExp(`${expression || '/'}$`).test(cleanPath(actual))
}

function navigationSurfaces(plans) {
  return (plans || []).flatMap((group) => (group.children || []).flatMap((workspace) => {
    const nodes = workspace.children?.length ? workspace.children : [workspace]
    return nodes.map((node) => ({
      path: node.path,
      status: node.status || workspace.status || 'planned',
      hidden: Boolean(node.hidden),
      disabled: Boolean(node.disabled),
      permissionCodes: [...new Set([
        node.permissionKey,
        ...(node.permissionAny || []),
        ...(node.permissionAll || [])
      ].filter(Boolean))]
    }))
  }))
}

/** Generate the deep-link guard for all query/panel surfaces sharing a Vue route. */
export function projectNavigationRoutePermissions(routes, plans, parentPath = '') {
  const surfaces = navigationSurfaces(plans).filter(
    (item) => item.path && !item.hidden && !item.disabled && ['implemented', 'partial'].includes(item.status)
  )
  const visit = (items, parent) => (items || []).map((route) => {
    const fullPath = joinPattern(parent, route.path)
    const matchingCodes = surfaces
      .filter((surface) => routeMatches(fullPath, surface.path))
      .flatMap((surface) => surface.permissionCodes)
    const existing = [
      route.meta?.permissionKey,
      ...(route.meta?.permissionAny || []),
      ...(route.meta?.permissionAll || [])
    ].filter(Boolean)
    const permissionAny = [...new Set([...existing, ...matchingCodes])].sort()
    const projected = {
      ...route,
      ...(permissionAny.length ? {
        meta: { ...(route.meta || {}), permissionAny, navigationProjected: true }
      } : {})
    }
    if (route.children?.length) projected.children = visit(route.children, fullPath)
    return projected
  })
  return visit(routes, parentPath)
}
