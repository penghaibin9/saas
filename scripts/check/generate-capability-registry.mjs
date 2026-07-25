#!/usr/bin/env node
/**
 * 从 navPlan / 系统管理目录 / 平台目录 / 真实路由索引自动生成 capability-registry.json。
 * 禁止人工维护第二份几百节点清单。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { buildRouteIndex, matchRouteExists } from './build-route-index.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '../..')
const OUT = path.join(ROOT, 'shared/generated/capability-registry.json')
const MANIFEST = path.join(ROOT, 'shared/contracts/module-manifest.json')

const ENTRY_TYPES = new Set([
  'WORKSPACE', 'TASK_QUEUE', 'FILTER_VIEW', 'ANALYTICS_VIEW', 'CONFIG_VIEW',
  'DETAIL', 'ACTION', 'CROSS_MODULE', 'EXTERNAL_DEPENDENCY',
])

const WORKBENCH_NO_PERM = new Set(['/', '/admin/help'])

function normalizeEntryType(raw, leaf, { isWorkspaceRecord }) {
  if (isWorkspaceRecord) return 'WORKSPACE'
  const v = String(raw || '').trim()
  if (ENTRY_TYPES.has(v)) return v
  const map = { WORKBENCH: 'WORKSPACE', CAPABILITY_ONLY: 'FILTER_VIEW' }
  if (map[v]) return map[v]
  if (leaf?.hidden) return 'DETAIL'
  if (leaf?.status === 'partial') return 'CONFIG_VIEW'
  // 叶子缺省：不要默认成 WORKSPACE（那是二级工作区专属）
  return 'CONFIG_VIEW'
}

function moduleKeyFromGroup(group) {
  return group.moduleKey || group.key || 'unknown'
}

function featureForModule(manifest, moduleKey) {
  const hit = (manifest.modules || []).find((m) => m.moduleKey === moduleKey
    || (m.aliases || []).includes(moduleKey))
  return hit?.featureKey || moduleKey
}

function firstLeafPermission(workspace) {
  for (const leaf of workspace.children || []) {
    if (leaf.permissionKey) return leaf.permissionKey
  }
  return null
}

function resolvePermission(cap, workspacePerm) {
  // 返回 { permissionKey, permissionPolicy, permissionExemptReason }
  if (cap.permissionKey) {
    return { permissionKey: cap.permissionKey, permissionPolicy: 'EXPLICIT', permissionExemptReason: null }
  }
  if (WORKBENCH_NO_PERM.has(cap.path)) {
    return {
      permissionKey: null,
      permissionPolicy: 'EXEMPT',
      permissionExemptReason: 'WORKBENCH_PUBLIC_ENTRY',
    }
  }
  if (String(cap.path || '').startsWith('/admin/planned/')) {
    return {
      permissionKey: null,
      permissionPolicy: 'EXEMPT',
      permissionExemptReason: 'PLANNED_PLACEHOLDER',
    }
  }
  if (cap.entryType === 'EXTERNAL_DEPENDENCY') {
    return {
      permissionKey: null,
      permissionPolicy: 'EXEMPT',
      permissionExemptReason: 'EXTERNAL_DEPENDENCY',
    }
  }
  if (cap.hidden || ['DETAIL', 'ACTION', 'FILTER_VIEW'].includes(cap.entryType)) {
    if (workspacePerm) {
      return {
        permissionKey: workspacePerm,
        permissionPolicy: 'INHERIT_WORKSPACE',
        permissionExemptReason: null,
      }
    }
    return {
      permissionKey: null,
      permissionPolicy: 'EXEMPT',
      permissionExemptReason: 'NON_SIDEBAR_NO_WORKSPACE_PERM',
    }
  }
  if (cap.entryType === 'WORKSPACE' && workspacePerm) {
    return {
      permissionKey: workspacePerm,
      permissionPolicy: 'INHERIT_FIRST_LEAF',
      permissionExemptReason: null,
    }
  }
  if (workspacePerm) {
    return {
      permissionKey: workspacePerm,
      permissionPolicy: 'INHERIT_WORKSPACE',
      permissionExemptReason: null,
    }
  }
  return {
    permissionKey: null,
    permissionPolicy: 'UNRESOLVED',
    permissionExemptReason: 'NO_PERMISSION_STRATEGY',
  }
}

async function loadNav() {
  const navUrl = pathToFileURL(path.join(ROOT, 'frontend/src/config/navPlan.js')).href
  const mod = await import(navUrl)
  return { NAV_PLAN: mod.NAV_PLAN, PLATFORM_PLAN: mod.PLATFORM_PLAN }
}

async function main() {
  const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'))
  const { NAV_PLAN, PLATFORM_PLAN } = await loadNav()
  const routeIndex = buildRouteIndex()
  // 同步落盘完整 route-index（含 exact/patterns/redirects/aliases），禁止只写统计壳
  const routeIndexOut = path.join(ROOT, 'shared/generated/route-index.json')
  fs.writeFileSync(routeIndexOut, JSON.stringify({
    generatedAt: new Date().toISOString(),
    exactCount: routeIndex.exact.size,
    patternCount: routeIndex.patterns.length,
    redirectCount: routeIndex.redirects.length,
    aliasCount: routeIndex.aliases.length,
    exact: [...routeIndex.exact].sort(),
    patterns: routeIndex.patterns,
    redirects: routeIndex.redirects,
    aliases: routeIndex.aliases,
  }, null, 2) + '\n', 'utf8')

  const capabilities = []
  const matchStats = { exact: 0, alias: 0, redirect: 0, param: 0, missing: 0, noPath: 0 }
  const permStats = { EXPLICIT: 0, INHERIT_FIRST_LEAF: 0, INHERIT_WORKSPACE: 0, EXEMPT: 0, UNRESOLVED: 0 }

  const groups = [...NAV_PLAN, PLATFORM_PLAN]
  for (const group of groups) {
    const schoolCenter = group.label
    const techModule = moduleKeyFromGroup(group)
    for (const workspace of group.children || []) {
      const wsKey = workspace.key
      const wsLabel = workspace.label
      const inheritedWsPerm = workspace.permissionKey || firstLeafPermission(workspace)

      if (workspace.path || (workspace.children || []).length === 0) {
        const match = workspace.path ? matchRouteExists(routeIndex, workspace.path) : { exists: false, matchType: 'missing' }
        if (!workspace.path) matchStats.noPath += 1
        else if (!match.exists) matchStats.missing += 1
        else matchStats[match.matchType] = (matchStats[match.matchType] || 0) + 1

        const base = {
          schoolCenter,
          techModule,
          workspaceKey: wsKey,
          workspaceLabel: wsLabel,
          capabilityKey: `${techModule}.${wsKey}`,
          label: wsLabel,
          path: workspace.path || null,
          entryType: 'WORKSPACE',
          permissionKey: workspace.permissionKey || null,
          featureKey: featureForModule(manifest, techModule),
          status: workspace.status || (workspace.path ? 'implemented' : 'planned'),
          hidden: false,
          dataOwner: techModule,
          routeExists: workspace.path ? !!match.exists : false,
          routeMatchType: workspace.path ? match.matchType : 'noPath',
          sidebarEligible: true,
        }
        const perm = resolvePermission(base, inheritedWsPerm)
        Object.assign(base, perm)
        permStats[perm.permissionPolicy] = (permStats[perm.permissionPolicy] || 0) + 1
        capabilities.push(base)
      }

      for (const leaf of workspace.children || []) {
        const entryType = normalizeEntryType(leaf.entryType, leaf, { isWorkspaceRecord: false })
        const match = leaf.path ? matchRouteExists(routeIndex, leaf.path) : { exists: false, matchType: 'missing' }
        if (!leaf.path) matchStats.noPath += 1
        else if (!match.exists) matchStats.missing += 1
        else matchStats[match.matchType] = (matchStats[match.matchType] || 0) + 1

        const sidebarEligible = !leaf.hidden
          && entryType !== 'DETAIL'
          && entryType !== 'ACTION'
          && entryType !== 'FILTER_VIEW'
        const base = {
          schoolCenter,
          techModule,
          workspaceKey: wsKey,
          workspaceLabel: wsLabel,
          capabilityKey: leaf.systemCapabilityKey
            || leaf.platformCapabilityKey
            || `${techModule}.${wsKey}.${(leaf.label || '').replace(/\s+/g, '_')}`,
          label: leaf.label,
          path: leaf.path || null,
          entryType,
          permissionKey: leaf.permissionKey || null,
          featureKey: featureForModule(manifest, techModule),
          status: leaf.status || 'planned',
          hidden: !!leaf.hidden,
          dataOwner: techModule,
          routeExists: leaf.path ? !!match.exists : false,
          routeMatchType: leaf.path ? match.matchType : 'noPath',
          sidebarEligible,
        }
        const perm = resolvePermission(base, inheritedWsPerm)
        Object.assign(base, perm)
        permStats[perm.permissionPolicy] = (permStats[perm.permissionPolicy] || 0) + 1
        capabilities.push(base)
      }
    }
  }

  const out = {
    generatedAt: new Date().toISOString(),
    generator: 'scripts/check/generate-capability-registry.mjs',
    manifestVersion: manifest.manifestVersion,
    schemaVersion: '1.1.0',
    count: capabilities.length,
    routeMatchStats: matchStats,
    permissionPolicyStats: permStats,
    capabilities,
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true })
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2) + '\n', 'utf8')
  console.log(`OK capability-registry count=${capabilities.length}`)
  console.log(`  routes: ${JSON.stringify(matchStats)}`)
  console.log(`  perms:  ${JSON.stringify(permStats)}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
