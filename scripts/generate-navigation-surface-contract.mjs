import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { NAV_PLAN, PLATFORM_PLAN } from '../frontend/src/config/navPlan.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputPath = path.join(root, 'shared', 'contracts', 'navigation-surface-contract.json')

function permissionsOf(node) {
  return [...new Set([
    node.permissionKey,
    ...(Array.isArray(node.permissionAny) ? node.permissionAny : []),
    ...(Array.isArray(node.permissionAll) ? node.permissionAll : [])
  ].filter(Boolean))].sort()
}

function surfaceKey(workspace, node, index) {
  return node.platformCapabilityKey
    || node.systemCapabilityKey
    || node.key
    || `${workspace.key}-${String(index + 1).padStart(2, '0')}`
}

function projectGroup(group) {
  const platformOnly = Boolean(group.platformOnly)
  return (group.children || []).flatMap((workspace) => {
    const nodes = workspace.children?.length ? workspace.children : [workspace]
    return nodes.map((node, index) => ({
      groupKey: group.key,
      groupLabel: group.label,
      moduleKey: group.moduleKey,
      workspaceKey: workspace.key,
      workspaceLabel: workspace.label,
      surfaceKey: surfaceKey(workspace, node, index),
      label: node.label,
      path: node.path || null,
      permissionKey: node.permissionKey || null,
      permissionAny: Array.isArray(node.permissionAny) ? [...node.permissionAny].sort() : [],
      permissionAll: Array.isArray(node.permissionAll) ? [...node.permissionAll].sort() : [],
      permissionCodes: permissionsOf(node),
      entryType: node.entryType || 'CONFIG_VIEW',
      status: node.status || workspace.status || 'planned',
      hidden: Boolean(node.hidden),
      disabled: Boolean(node.disabled),
      platformOnly
    }))
  })
}

export function buildNavigationSurfaceContract() {
  const surfaces = [...NAV_PLAN, PLATFORM_PLAN].flatMap(projectGroup)
  const digest = crypto.createHash('sha256').update(JSON.stringify(surfaces)).digest('hex')
  return {
    schemaVersion: 1,
    authority: 'GENERATED_FROM_NAV_PLAN_AND_PLATFORM_PLAN',
    generatedFrom: [
      'frontend/src/config/navPlan.js#NAV_PLAN',
      'frontend/src/config/navPlan.js#PLATFORM_PLAN'
    ],
    digest,
    counts: {
      total: surfaces.length,
      production: surfaces.filter((item) => ['implemented', 'partial'].includes(item.status)).length,
      productionVisible: surfaces.filter((item) => ['implemented', 'partial'].includes(item.status) && !item.hidden && !item.disabled).length,
      hidden: surfaces.filter((item) => item.hidden).length,
      planned: surfaces.filter((item) => item.status === 'planned').length,
      school: surfaces.filter((item) => !item.platformOnly).length,
      platform: surfaces.filter((item) => item.platformOnly).length
    },
    surfaces
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const rendered = `${JSON.stringify(buildNavigationSurfaceContract(), null, 2)}\n`
  if (process.argv.includes('--check')) {
    const checkedIn = fs.existsSync(outputPath) ? fs.readFileSync(outputPath, 'utf8') : ''
    if (checkedIn !== rendered) {
      console.error('navigation-surface-contract.json drifted; run npm run contract:navigation:generate')
      process.exitCode = 1
    } else {
      console.log('navigation surface contract is current')
    }
  } else {
    fs.writeFileSync(outputPath, rendered, 'utf8')
    console.log(`wrote ${path.relative(root, outputPath)}`)
  }
}
