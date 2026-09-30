import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { createServer } from 'vite'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = path.resolve(frontendRoot, '..')
const contract = JSON.parse(
  fs.readFileSync(path.join(repoRoot, 'shared/contracts/navigation-surface-contract.json'), 'utf8')
)

const definitions = [
  ['/src/router/coreControl.routes.js', 'coreControlRoutes'],
  ['/src/modules/student/student.routes.js', 'studentRoutes'],
  ['/src/modules/orientation/orientation.routes.js', 'default'],
  ['/src/modules/campusService/campusService.routes.js', 'default'],
  ['/src/modules/academicAffairs/routes/academic.routes.js', 'default'],
  ['/src/modules/academicAffairs/academic-affairs.routes.js', 'academicAffairsRoutes'],
  ['/src/modules/internship/routes.js', 'default'],
  ['/src/modules/graduation/routes.js', 'default'],
  ['/src/modules/employment/employment.routes.js', 'default'],
  ['/src/modules/dataCenter/dataCenter.routes.js', 'default'],
  ['/src/modules/approval/approval.routes.js', 'default'],
  ['/src/modules/system/system.routes.js', 'default'],
  ['/src/modules/platform/platform.routes.js', 'default'],
  ['/src/modules/studentAffairs/studentAffairs.routes.js', 'default'],
  ['/src/modules/messageCenter/message-center.routes.js', 'default']
]

function cleanPath(value) {
  const withoutQuery = String(value || '').split('?')[0]
  const normalized = `/${withoutQuery}`.replace(/\/{2,}/g, '/').replace(/\/$/, '')
  return normalized || '/'
}

function cleanPattern(value) {
  const normalized = `/${String(value || '')}`.replace(/\/{2,}/g, '/').replace(/\/$/, '')
  return normalized || '/'
}

function joinPath(parent, child) {
  if (String(child || '').startsWith('/')) return cleanPattern(child)
  return cleanPattern(`${parent || ''}/${child || ''}`)
}

function flattenRoutes(routes, parentPath = '', parentMeta = {}) {
  return (routes || []).flatMap((route) => {
    const fullPath = joinPath(parentPath, route.path)
    const meta = { ...parentMeta, ...(route.meta || {}) }
    return [
      { path: fullPath, meta, redirect: route.redirect || null, name: route.name || null },
      ...flattenRoutes(route.children || [], fullPath, meta)
    ]
  })
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

const server = await createServer({
  root: frontendRoot,
  server: { middlewareMode: true },
  optimizeDeps: { noDiscovery: true },
  appType: 'custom'
})
try {
  const loaded = []
  for (const [modulePath, exportName] of definitions) {
    const module = await server.ssrLoadModule(modulePath)
    const value = module[exportName]
    assert.ok(value, `${modulePath} does not export ${exportName}`)
    loaded.push(...(Array.isArray(value) ? value : [value]))
  }
  const projectionModule = await server.ssrLoadModule('/src/router/navigationRouteProjection.js')
  const navModule = await server.ssrLoadModule('/src/config/navPlan.js')
  const projected = projectionModule.projectNavigationRoutePermissions(
    loaded,
    [...navModule.NAV_PLAN, navModule.PLATFORM_PLAN]
  )
  const routes = flattenRoutes(projected)

  const production = contract.surfaces.filter(
    (item) => !item.hidden && !item.disabled && ['implemented', 'partial'].includes(item.status)
  )
  const missingRoutes = []
  const permissionDrift = []
  for (const surface of production) {
    const candidates = routes.filter((route) => routeMatches(route.path, surface.path))
    if (!candidates.length) {
      missingRoutes.push({ surfaceKey: surface.surfaceKey, path: surface.path })
      continue
    }
    if (!surface.permissionCodes.length) continue
    const matched = candidates.some(({ meta }) => {
      const routeCodes = new Set([
        meta.permissionKey,
        ...(meta.permissionAny || []),
        ...(meta.permissionAll || [])
      ].filter(Boolean))
      return surface.permissionCodes.every((code) => routeCodes.has(code))
    })
    if (!matched) {
      permissionDrift.push({
        surfaceKey: surface.surfaceKey,
        path: surface.path,
        navigationPermissions: surface.permissionCodes,
        routePermissions: candidates.map(({ meta }) => ({
          permissionKey: meta.permissionKey || null,
          permissionAny: meta.permissionAny || [],
          permissionAll: meta.permissionAll || []
        }))
      })
    }
  }

  assert.deepEqual(missingRoutes, [], `production navigation routes missing:\n${JSON.stringify(missingRoutes, null, 2)}`)
  assert.deepEqual(permissionDrift, [], `navigation/route permission drift:\n${JSON.stringify(permissionDrift, null, 2)}`)
  console.log(`navigation route parity passed for ${production.length} production-visible surfaces`)
} finally {
  await server.close()
}
