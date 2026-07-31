#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const PROTOTYPE_ROOT = path.resolve(TOOL_DIR, '..')
const REPO_ROOT = path.resolve(PROTOTYPE_ROOT, '../../..')
const NAV_PATH = path.join(REPO_ROOT, 'frontend/src/config/navPlan.js')
const MANIFEST_PATH = path.join(PROTOTYPE_ROOT, 'manifest-parts/310-internship-key.json')
const reportArg = process.argv.slice(2).find((value) => value.startsWith('--report='))
const reportPath = reportArg ? path.resolve(process.cwd(), reportArg.slice('--report='.length)) : null

const errors = []
const warnings = []
const notes = []
const fail = (code, message, detail = {}) => errors.push({ code, message, ...detail })
const warn = (code, message, detail = {}) => warnings.push({ code, message, ...detail })

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch (error) {
    fail('INVALID_JSON', `${path.relative(REPO_ROOT, file)} 不是有效 JSON：${error.message}`)
    return null
  }
}

function unescapeJs(value) {
  return String(value || '').replace(/\\'/g, "'").replace(/\\\\/g, '\\')
}

function findMatchingBracket(text, openIndex, openChar = '[', closeChar = ']') {
  let depth = 0
  let quote = ''
  let escaped = false
  for (let index = openIndex; index < text.length; index += 1) {
    const char = text[index]
    if (quote) {
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if (char === quote) quote = ''
      continue
    }
    if (char === "'" || char === '"' || char === '`') {
      quote = char
      continue
    }
    if (char === openChar) depth += 1
    else if (char === closeChar) {
      depth -= 1
      if (depth === 0) return index
    }
  }
  return -1
}

function parseInternshipNav(source) {
  const startMarker = "grp('internship', '岗位实习中心', 'internship', ["
  const start = source.indexOf(startMarker)
  const end = source.indexOf('/* ═══════════ 一级⑥', start)
  if (start < 0 || end < 0) {
    fail('INTERNSHIP_BLOCK_NOT_FOUND', '无法在 navPlan.js 中定位岗位实习组')
    return []
  }
  const block = source.slice(start, end)
  const modules = []
  const moduleRegex = /mod\('([^']+)',\s*'([^']+)',\s*'([^']*)',\s*\[/g
  let match
  while ((match = moduleRegex.exec(block))) {
    const openIndex = block.indexOf('[', match.index + match[0].length - 1)
    const closeIndex = findMatchingBracket(block, openIndex)
    if (closeIndex < 0) {
      fail('MODULE_ARRAY_UNCLOSED', `模块 ${match[1]} 的 children 数组未闭合`)
      continue
    }
    const childrenSource = block.slice(openIndex + 1, closeIndex)
    const leaves = []
    const leafRegex = /\b(I|H|PA)\(\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'(?:\s*,\s*'((?:\\'|[^'])*)')?/g
    let leaf
    while ((leaf = leafRegex.exec(childrenSource))) {
      leaves.push({
        factory: leaf[1],
        label: unescapeJs(leaf[2]),
        route: unescapeJs(leaf[3]),
        permissionKey: unescapeJs(leaf[4]),
        entryType: unescapeJs(leaf[5] || '')
      })
    }
    modules.push({
      moduleKey: match[1],
      moduleLabel: match[2],
      modulePath: match[3],
      leaves
    })
    moduleRegex.lastIndex = closeIndex + 1
  }
  return modules
}

if (!fs.existsSync(NAV_PATH)) fail('NAV_NOT_FOUND', `生产导航不存在：${NAV_PATH}`)
if (!fs.existsSync(MANIFEST_PATH)) fail('MANIFEST_NOT_FOUND', `岗位实习 Manifest 不存在：${MANIFEST_PATH}`)

const navSource = fs.existsSync(NAV_PATH) ? fs.readFileSync(NAV_PATH, 'utf8') : ''
const modules = parseInternshipNav(navSource)
const manifest = fs.existsSync(MANIFEST_PATH) ? readJson(MANIFEST_PATH) : null
const navLeaves = modules.flatMap((module) => module.leaves.map((leaf) => ({ ...leaf, moduleKey: module.moduleKey, moduleLabel: module.moduleLabel })))
const uniqueNavRoutes = new Map()
for (const leaf of navLeaves) {
  if (!uniqueNavRoutes.has(leaf.route)) uniqueNavRoutes.set(leaf.route, [])
  uniqueNavRoutes.get(leaf.route).push(leaf)
}

const expectedModules = [
  'in-workbench', 'in-batch-rules', 'in-students', 'in-enterprise-position',
  'in-match-assign', 'in-apply-agreement', 'in-attendance-leave', 'in-weekly-task',
  'in-guidance-visit', 'in-risk', 'in-eval-score', 'in-employment-archive-stats'
]

if (modules.length !== 12) fail('MODULE_COUNT_MISMATCH', `生产导航解析到 ${modules.length} 个岗位实习二级模块，期望 12`, { modules: modules.map((item) => item.moduleKey) })
for (const key of expectedModules) if (!modules.some((module) => module.moduleKey === key)) fail('MISSING_PRODUCTION_MODULE', `生产导航缺少模块 ${key}`)
if (navLeaves.length !== 101) fail('LEAF_COUNT_MISMATCH', `生产导航解析到 ${navLeaves.length} 个三级叶子，冻结契约期望 101`)
if (uniqueNavRoutes.size !== 99) fail('UNIQUE_ROUTE_COUNT_MISMATCH', `生产导航解析到 ${uniqueNavRoutes.size} 个唯一 URL，冻结契约期望 99`)

const duplicateNavRoutes = [...uniqueNavRoutes.entries()].filter(([, leaves]) => leaves.length > 1)
const expectedAliases = new Map((manifest?.routeAudit?.intentionalAliases || []).map((item) => [item.route, item.labels]))
if (duplicateNavRoutes.length !== 2) fail('ALIAS_COUNT_MISMATCH', `生产导航出现 ${duplicateNavRoutes.length} 个共享 URL，冻结契约期望 2`)
for (const [route, leaves] of duplicateNavRoutes) {
  const labels = leaves.map((leaf) => leaf.label).sort()
  const declared = [...(expectedAliases.get(route) || [])].sort()
  if (!declared.length) fail('UNDECLARED_ROUTE_ALIAS', `共享 URL 未在 Manifest 显式声明：${route}`, { labels })
  else if (JSON.stringify(labels) !== JSON.stringify(declared)) fail('ALIAS_LABEL_MISMATCH', `共享 URL 标签与声明不一致：${route}`, { production: labels, manifest: declared })
}
for (const route of expectedAliases.keys()) if (!uniqueNavRoutes.has(route) || uniqueNavRoutes.get(route).length < 2) fail('STALE_ALIAS_DECLARATION', `Manifest 声明的共享 URL 在生产导航中不存在或不再共享：${route}`)

const ownerEntries = Array.isArray(manifest?.routes) ? manifest.routes : []
const ownerRoutes = new Map()
const moduleOwners = new Map()
for (const entry of ownerEntries) {
  const refs = [entry.route, ...(entry.coveredRoutes || [])]
  if (!entry.moduleKey) fail('OWNER_WITHOUT_MODULE', `Manifest 条目缺少 moduleKey：${entry.title || entry.route}`)
  if (moduleOwners.has(entry.moduleKey)) fail('DUPLICATE_MODULE_OWNER', `Manifest 重复声明模块 owner：${entry.moduleKey}`)
  moduleOwners.set(entry.moduleKey, entry)
  for (const route of refs) {
    if (ownerRoutes.has(route)) fail('DUPLICATE_ROUTE_OWNER', `唯一 URL 被多个原型重复认领：${route}`, { first: ownerRoutes.get(route).moduleKey, second: entry.moduleKey })
    ownerRoutes.set(route, entry)
  }
  const htmlPath = path.resolve(PROTOTYPE_ROOT, entry.html || '')
  if (!entry.html || !fs.existsSync(htmlPath)) fail('OWNER_HTML_MISSING', `模块 ${entry.moduleKey} 的 HTML 不存在：${entry.html || '(missing)'}`)
  for (const key of ['fieldContract', 'statusContract', 'apiParameterContract']) {
    if (!Array.isArray(entry[key]) || !entry[key].length) fail('EMPTY_ROUTE_CONTRACT', `模块 ${entry.moduleKey} 缺少 ${key}`)
  }
  if (!Array.isArray(entry.permissionCandidates) || !entry.permissionCandidates.length) fail('EMPTY_PERMISSION_CONTRACT', `模块 ${entry.moduleKey} 缺少 permissionCandidates`)
}

if (ownerEntries.length !== 12) fail('OWNER_MODULE_COUNT_MISMATCH', `Manifest 有 ${ownerEntries.length} 个模块 owner，期望 12`)
for (const key of expectedModules) if (!moduleOwners.has(key)) fail('MISSING_MODULE_OWNER', `Manifest 缺少模块 owner：${key}`)
if (ownerRoutes.size !== 99) fail('OWNER_ROUTE_COUNT_MISMATCH', `Manifest 认领 ${ownerRoutes.size} 个唯一 URL，期望 99`)

for (const [route, leaves] of uniqueNavRoutes) {
  const owner = ownerRoutes.get(route)
  if (!owner) {
    fail('UNCOVERED_PRODUCTION_ROUTE', `生产三级 URL 未被原型认领：${route}`, { leaves })
    continue
  }
  const permissions = new Set(owner.permissionCandidates || [])
  for (const leaf of leaves) {
    if (leaf.permissionKey && !permissions.has(leaf.permissionKey)) {
      fail('PERMISSION_CONTRACT_MISMATCH', `URL ${route} 的生产权限 ${leaf.permissionKey} 未进入 owner ${owner.moduleKey} 的权限契约`, { label: leaf.label, owner: owner.moduleKey })
    }
    if (!leaf.entryType) warn('MISSING_PRODUCTION_ENTRY_TYPE', `生产三级叶子没有 entryType：${leaf.moduleKey} / ${leaf.label}`, { route })
  }
}
for (const [route, owner] of ownerRoutes) if (!uniqueNavRoutes.has(route)) fail('STALE_MANIFEST_ROUTE', `Manifest 认领的 URL 不在生产岗位实习导航：${route}`, { owner: owner.moduleKey })

const auditExpectations = manifest?.routeAudit || {}
if (auditExpectations.productionLeafEntriesExpected !== navLeaves.length) fail('DECLARED_LEAF_EXPECTATION_MISMATCH', 'routeAudit.productionLeafEntriesExpected 与生产解析结果不一致')
if (auditExpectations.uniqueRouteRefsExpected !== uniqueNavRoutes.size) fail('DECLARED_ROUTE_EXPECTATION_MISMATCH', 'routeAudit.uniqueRouteRefsExpected 与生产解析结果不一致')
if (auditExpectations.ownerRouteRefsExpected !== ownerRoutes.size) fail('DECLARED_OWNER_EXPECTATION_MISMATCH', 'routeAudit.ownerRouteRefsExpected 与 Manifest 认领结果不一致')

const routeRows = [...uniqueNavRoutes.entries()].map(([route, leaves]) => {
  const owner = ownerRoutes.get(route)
  return {
    route,
    leafCount: leaves.length,
    labels: leaves.map((leaf) => leaf.label),
    productionModules: [...new Set(leaves.map((leaf) => leaf.moduleKey))],
    permissions: [...new Set(leaves.map((leaf) => leaf.permissionKey).filter(Boolean))],
    entryTypes: [...new Set(leaves.map((leaf) => leaf.entryType).filter(Boolean))],
    ownerModule: owner?.moduleKey || '',
    ownerHtml: owner?.html || '',
    fieldContractCount: owner?.fieldContract?.length || 0,
    statusContractCount: owner?.statusContract?.length || 0,
    apiParameterContractCount: owner?.apiParameterContract?.length || 0,
    status: owner ? 'COVERED' : 'MISSING'
  }
})

const counts = {
  productionModules: modules.length,
  productionLeafEntries: navLeaves.length,
  productionUniqueRoutes: uniqueNavRoutes.size,
  intentionalAliasRoutes: duplicateNavRoutes.length,
  manifestOwnerModules: ownerEntries.length,
  manifestOwnedRoutes: ownerRoutes.size,
  coveredRoutes: routeRows.filter((row) => row.status === 'COVERED').length,
  errors: errors.length,
  warnings: warnings.length
}
const report = {
  generatedAt: new Date().toISOString(),
  sourceNav: path.relative(REPO_ROOT, NAV_PATH),
  sourceManifest: path.relative(REPO_ROOT, MANIFEST_PATH),
  counts,
  modules: modules.map((module) => ({ moduleKey: module.moduleKey, moduleLabel: module.moduleLabel, leafEntries: module.leaves.length, uniqueRoutes: new Set(module.leaves.map((leaf) => leaf.route)).size })),
  duplicateNavRoutes: duplicateNavRoutes.map(([route, leaves]) => ({ route, labels: leaves.map((leaf) => leaf.label) })),
  errors,
  warnings,
  notes,
  routes: routeRows
}

if (reportPath) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true })
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
  const mdPath = reportPath.replace(/\.json$/i, '.md')
  const md = [
    '# 岗位实习 99 URL 机器审计',
    '',
    `- 生产二级模块：**${counts.productionModules}**`,
    `- 生产三级叶子：**${counts.productionLeafEntries}**`,
    `- 唯一 URL：**${counts.productionUniqueRoutes}**`,
    `- 显式共享 URL：**${counts.intentionalAliasRoutes}**`,
    `- Manifest owner：**${counts.manifestOwnerModules}**`,
    `- 已认领 URL：**${counts.manifestOwnedRoutes}**`,
    `- 错误：**${counts.errors}**`,
    `- 警告：**${counts.warnings}**`,
    '',
    '## 二级模块',
    '',
    '| 模块 | 叶子 | 唯一 URL |',
    '|---|---:|---:|',
    ...report.modules.map((module) => `| ${module.moduleLabel} (${module.moduleKey}) | ${module.leafEntries} | ${module.uniqueRoutes} |`),
    '',
    ...(errors.length ? ['## 错误', '', ...errors.map((item) => `- **${item.code}**：${item.message}`), ''] : []),
    ...(warnings.length ? ['## 警告', '', ...warnings.map((item) => `- **${item.code}**：${item.message}`), ''] : []),
    '## URL 覆盖',
    '',
    '| URL | 生产标签 | Owner | HTML |',
    '|---|---|---|---|',
    ...routeRows.map((row) => `| \`${row.route.replace(/\|/g, '\\|')}\` | ${row.labels.join(' / ')} | ${row.ownerModule || 'MISSING'} | ${row.ownerHtml || 'MISSING'} |`),
    ''
  ].join('\n')
  fs.writeFileSync(mdPath, `${md}\n`)
}

console.log(JSON.stringify(counts, null, 2))
for (const item of errors) console.error(`ERROR [${item.code}] ${item.message}`)
for (const item of warnings) console.warn(`WARN  [${item.code}] ${item.message}`)
if (errors.length) process.exit(1)
