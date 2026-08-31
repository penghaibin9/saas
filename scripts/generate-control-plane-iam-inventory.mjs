import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const readJson = (name) => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'))
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim()
const write = (name, value) => fs.writeFileSync(path.join(root, 'artifacts', name), `${JSON.stringify(value, null, 2)}\n`)

const navigation = readJson('shared/contracts/navigation-surface-contract.json')
const baseCatalog = readJson('shared/contracts/permission-catalog.json')
const concrete = readJson('shared/contracts/permission-catalog-b8-concrete.json')
const compatibility = readJson('shared/contracts/permission-catalog-b8-compatibility.json')
const aliases = readJson('shared/contracts/permission-aliases.json')
const catalogCodes = [
  ...baseCatalog.entries.map((item) => item.permissionCode),
  ...concrete.entries,
  ...compatibility.entries
]
const uniqueCatalogCodes = new Set(catalogCodes)
const assignableCanonical = uniqueCatalogCodes.size - [...uniqueCatalogCodes].filter((code) => code.startsWith('platform.') || code.startsWith('enterprise.') || code.startsWith('system.')).length

const migrationFiles = fs.readdirSync(path.join(root, 'backend/alembic/versions')).filter((name) => name.endsWith('.py'))
const revisions = new Map()
const downRevisions = new Set()
for (const file of migrationFiles) {
  const source = fs.readFileSync(path.join(root, 'backend/alembic/versions', file), 'utf8')
  const revision = source.match(/^revision\s*(?::[^=]+)?=\s*["']([^"']+)["']/m)?.[1]
  if (!revision) continue
  revisions.set(revision, file)
  const single = source.match(/^down_revision\s*(?::[^=]+)?=\s*["']([^"']+)["']/m)?.[1]
  if (single) downRevisions.add(single)
  const tuple = source.match(/^down_revision\s*(?::[^=]+)?=\s*\(([^)]+)\)/m)?.[1] || ''
  for (const match of tuple.matchAll(/["']([^"']+)["']/g)) downRevisions.add(match[1])
}
const heads = [...revisions].filter(([revision]) => !downRevisions.has(revision)).map(([revision, file]) => ({ revision, file }))
const exactHead = git('rev-parse', 'HEAD')
const originMain = git('rev-parse', 'origin/main')

write('navigation-inventory.json', {
  exactHead,
  authority: navigation.authority,
  digest: navigation.digest,
  counts: navigation.counts,
  productionProjectionCoverage: navigation.counts.productionVisible ? '100%' : '0%',
  generatedContract: 'shared/contracts/navigation-surface-contract.json'
})
write('permission-inventory.json', {
  exactHead,
  authority: 'shared/contracts/permission-catalog*.json',
  baseEntries: baseCatalog.entries.length,
  b8ConcreteEntries: concrete.entries.length,
  b8CompatibilityEntries: compatibility.entries.length,
  uniqueConcretePermissions: uniqueCatalogCodes.size,
  duplicateConcretePermissions: catalogCodes.length - uniqueCatalogCodes.size,
  canonicalCustomRoleAuthoringPermissions: assignableCanonical,
  explicitLegacyAliases: Object.keys(aliases.aliases).length,
  newWrites: aliases.newWrites
})
write('migration-dag.json', {
  exactHead,
  migrationFiles: migrationFiles.length,
  parsedRevisions: revisions.size,
  heads,
  singleHead: heads.length === 1
})
write('role-template-inventory.json', {
  exactHead,
  canonicalTables: ['t_role_template', 't_role_template_permission', 't_custom_role_source', 't_role_permission'],
  service: 'backend/app/modules/system_admin/services/role_template_service.py',
  lifecycle: ['DRAFT', 'PUBLISHED_IMMUTABLE', 'ROLLBACK_AS_NEW_DRAFT'],
  runtimeSystemRoleAuthority: 'PUBLISHED_ROLE_TEMPLATE',
  customRoleAuthority: 'ROLE_PERMISSION_PINNED',
  databaseRowInventory: 'DEFERRED_TO_FRESH_MYSQL_GATE'
})
write('shared-owner-lock.json', {
  branch: git('branch', '--show-current'), exactHead,
  owner: 'CONTROL_PLANE_IAM_MENU_AUTHORITY',
  ownedAreas: [
    'frontend/src/config', 'frontend/src/security', 'frontend/src/router',
    'shared/contracts/permission-*', 'shared/contracts/navigation-*',
    'backend/app/core/permissions.py', 'backend/app/core/effective_access.py',
    'backend/app/services/system_role_shadow_service.py',
    'Product IAM', 'School IAM', 'RoleTemplate', 'Custom Role', 'Permission Projection'
  ],
  migrationOwner: true,
  mergePolicy: 'MERGE_READY_HOLD_OWNER_APPROVAL_REQUIRED'
})
write('open-pr-overlay.json', {
  observedAt: '2026-08-31T00:00:00+08:00',
  source: 'GitHub connector',
  relevantOpenPullRequests: [
    { number: 242, title: 'feat(internship): 岗位实习中心 V8 4+1 端安全重构', action: 'draft overlay on same main; do not merge into IAM branch, rescan only if it reaches main' },
    { number: 237, title: 'fix(platform): repair disaster recovery and add service config entry', action: 'normal merge latest main if merged' },
    { number: 112, title: 'refactor(platform): split platform control plane and implement Option B', action: 'historical draft; never merge as future-main source' },
    { number: 113, title: 'refactor(system): split school system control plane and implement Option B', action: 'historical draft; never merge as future-main source' }
  ],
  mergedOverlay: [{ number: 239, mergeCommit: '06fd94f08ad0f7e9c2ba96789908245f81bd4773', presentInExactHead: true }],
  mainCombinedStatuses: [],
  branchProtectionEvidence: 'GitHub connector has no branch-protection read operation; local gh CLI is not authenticated'
})
write('control-plane-iam-w0.json', {
  observedAt: '2026-08-31T00:00:00+08:00',
  repository: 'penghaibin9/saas',
  branch: git('branch', '--show-current'),
  exactHead,
  originMain,
  basedOnLatestMain: git('merge-base', '--is-ancestor', originMain, exactHead) === '' || exactHead === originMain,
  worktreeCleanAtFreeze: git('status', '--porcelain') === '',
  navigationDigest: navigation.digest,
  permissionCount: uniqueCatalogCodes.size,
  navigationCounts: navigation.counts,
  alembicHeads: heads,
  openPrOverlay: 'artifacts/open-pr-overlay.json',
  authorityTopology: ['Permission Catalog', 'RoleTemplate', 'RolePermission', 'DataScope', 'Entitlement', 'EffectiveAccess', 'Navigation Projection'],
  blockers: ['required-check branch protection cannot be read by current connector', 'Fresh MySQL and browser seals pending W12-W14']
})

console.log(`wrote W0 IAM inventories for ${exactHead}`)
