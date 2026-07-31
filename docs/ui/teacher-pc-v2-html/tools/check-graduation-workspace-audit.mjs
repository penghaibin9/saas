#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const PROTOTYPE_ROOT = path.resolve(TOOL_DIR, '..')
const REPO_ROOT = path.resolve(TOOL_DIR, '../../../..')
const SOURCE_PATH = path.join(REPO_ROOT, 'frontend/src/modules/graduation/config/graduationWorkspaces.js')
const MANIFEST_PATH = path.join(PROTOTYPE_ROOT, 'manifest-parts/320-graduation.json')
const reportArg = process.argv.slice(2).find((value) => value.startsWith('--report='))
const reportPath = reportArg ? path.resolve(process.cwd(), reportArg.slice('--report='.length)) : null

const errors = []
const notes = []

function fail(code, message, detail = {}) {
  errors.push({ code, message, ...detail })
}

function note(code, message, detail = {}) {
  notes.push({ code, message, ...detail })
}

function readText(file, label) {
  if (!fs.existsSync(file)) {
    fail('MISSING_FILE', `缺少${label}：${file}`)
    return ''
  }
  return fs.readFileSync(file, 'utf8')
}

function readJson(file, label) {
  const text = readText(file, label)
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch (error) {
    fail('INVALID_JSON', `${label}不是有效 JSON：${error.message}`)
    return null
  }
}

function extractArrayLiteral(source, marker) {
  const markerIndex = source.indexOf(marker)
  if (markerIndex < 0) {
    fail('SOURCE_MARKER_MISSING', `生产事实源缺少标记：${marker}`)
    return null
  }
  const start = source.indexOf('[', markerIndex + marker.length)
  if (start < 0) {
    fail('SOURCE_ARRAY_MISSING', '生产事实源没有找到工作区数组起点')
    return null
  }

  let depth = 0
  let quote = null
  let escaped = false
  let lineComment = false
  let blockComment = false

  for (let index = start; index < source.length; index += 1) {
    const char = source[index]
    const next = source[index + 1]

    if (lineComment) {
      if (char === '\n') lineComment = false
      continue
    }
    if (blockComment) {
      if (char === '*' && next === '/') {
        blockComment = false
        index += 1
      }
      continue
    }
    if (quote) {
      if (escaped) {
        escaped = false
        continue
      }
      if (char === '\\') {
        escaped = true
        continue
      }
      if (char === quote) quote = null
      continue
    }

    if (char === '/' && next === '/') {
      lineComment = true
      index += 1
      continue
    }
    if (char === '/' && next === '*') {
      blockComment = true
      index += 1
      continue
    }
    if (char === "'" || char === '"' || char === '`') {
      quote = char
      continue
    }
    if (char === '[') depth += 1
    if (char === ']') {
      depth -= 1
      if (depth === 0) return source.slice(start, index + 1)
    }
  }

  fail('SOURCE_ARRAY_UNCLOSED', '生产工作区数组没有闭合')
  return null
}

function evaluateWorkspaces(source) {
  const literal = extractArrayLiteral(source, 'export const GRADUATION_WORKSPACES =')
  if (!literal) return []
  try {
    const value = vm.runInNewContext(`(${literal})`, Object.create(null), { timeout: 1000 })
    if (!Array.isArray(value)) {
      fail('SOURCE_NOT_ARRAY', '生产工作区表达式结果不是数组')
      return []
    }
    return value
  } catch (error) {
    fail('SOURCE_EVALUATION_FAILED', `无法解析生产工作区数组：${error.message}`)
    return []
  }
}

function sameSet(left, right) {
  if (left.size !== right.size) return false
  for (const value of left) if (!right.has(value)) return false
  return true
}

function sorted(values) {
  return [...values].sort((a, b) => a.localeCompare(b, 'zh-CN'))
}

const source = readText(SOURCE_PATH, '毕业设计生产工作区事实源')
const manifest = readJson(MANIFEST_PATH, '毕业设计原型 Manifest')
const workspaces = source ? evaluateWorkspaces(source) : []
const entries = Array.isArray(manifest?.routes) ? manifest.routes : []

const expected = {
  workspaceCount: 8,
  leafCount: 50,
  uniqueUrlCount: 48,
  sharedUrlCount: 2
}

const productionLeaves = []
const productionByKey = new Map()
for (const workspace of workspaces) {
  if (!workspace?.key || typeof workspace.key !== 'string') {
    fail('WORKSPACE_WITHOUT_KEY', '生产工作区缺少 key', { workspace })
    continue
  }
  if (productionByKey.has(workspace.key)) {
    fail('DUPLICATE_WORKSPACE_KEY', `生产工作区 key 重复：${workspace.key}`)
  }
  productionByKey.set(workspace.key, workspace)
  if (!Array.isArray(workspace.children)) {
    fail('WORKSPACE_WITHOUT_CHILDREN', `生产工作区没有 children：${workspace.key}`)
    continue
  }
  workspace.children.forEach((leaf, index) => {
    productionLeaves.push({
      workspaceKey: workspace.key,
      workspaceLabel: workspace.label,
      index,
      label: leaf?.label,
      path: leaf?.path,
      permissionKey: leaf?.permissionKey
    })
    if (!leaf?.path || typeof leaf.path !== 'string') {
      fail('LEAF_WITHOUT_PATH', `${workspace.key} 的第 ${index + 1} 个叶子缺少 path`)
    }
  })
}

const urlOwners = new Map()
for (const leaf of productionLeaves) {
  if (!leaf.path) continue
  if (!urlOwners.has(leaf.path)) urlOwners.set(leaf.path, new Set())
  urlOwners.get(leaf.path).add(leaf.workspaceKey)
}
const sharedUrls = new Map([...urlOwners].filter(([, owners]) => owners.size > 1))

if (workspaces.length !== expected.workspaceCount) {
  fail('WORKSPACE_COUNT', `生产工作区数量为 ${workspaces.length}，期望 ${expected.workspaceCount}`)
}
if (productionLeaves.length !== expected.leafCount) {
  fail('LEAF_COUNT', `生产三级叶子数量为 ${productionLeaves.length}，期望 ${expected.leafCount}`)
}
if (urlOwners.size !== expected.uniqueUrlCount) {
  fail('UNIQUE_URL_COUNT', `生产唯一 URL 数量为 ${urlOwners.size}，期望 ${expected.uniqueUrlCount}`)
}
if (sharedUrls.size !== expected.sharedUrlCount) {
  fail('SHARED_URL_COUNT', `生产共享 URL 数量为 ${sharedUrls.size}，期望 ${expected.sharedUrlCount}`)
}

const declaredSource = manifest?.productionSource || {}
for (const key of Object.keys(expected)) {
  if (declaredSource[key] !== expected[key]) {
    fail('DECLARED_COUNT_MISMATCH', `Manifest productionSource.${key}=${declaredSource[key]}，期望 ${expected[key]}`, { key })
  }
}

if (entries.length !== expected.workspaceCount) {
  fail('MANIFEST_ENTRY_COUNT', `320 Manifest 工作区条目为 ${entries.length}，期望 ${expected.workspaceCount}`)
}

const manifestByKey = new Map()
const htmlOwners = new Map()
for (const entry of entries) {
  if (!entry?.workspaceKey) {
    fail('MANIFEST_ENTRY_WITHOUT_KEY', '320 Manifest 条目缺少 workspaceKey', { entry })
    continue
  }
  if (manifestByKey.has(entry.workspaceKey)) {
    fail('DUPLICATE_MANIFEST_KEY', `320 Manifest workspaceKey 重复：${entry.workspaceKey}`)
  }
  manifestByKey.set(entry.workspaceKey, entry)

  if (!entry.html) {
    fail('MANIFEST_ENTRY_WITHOUT_HTML', `${entry.workspaceKey} 缺少 html`)
  } else {
    const htmlPath = path.resolve(PROTOTYPE_ROOT, entry.html)
    if (!htmlPath.startsWith(`${PROTOTYPE_ROOT}${path.sep}`) || !fs.existsSync(htmlPath)) {
      fail('MISSING_WORKSPACE_HTML', `${entry.workspaceKey} 的 HTML 不存在：${entry.html}`)
    }
    if (!htmlOwners.has(entry.html)) htmlOwners.set(entry.html, [])
    htmlOwners.get(entry.html).push(entry.workspaceKey)
  }
}

for (const [html, owners] of htmlOwners) {
  if (owners.length > 1) {
    fail('DUPLICATE_HTML_OWNER', `多个毕业设计工作区复用同一 HTML：${html}`, { owners })
  }
}

for (const workspace of workspaces) {
  const entry = manifestByKey.get(workspace.key)
  if (!entry) {
    fail('MISSING_MANIFEST_WORKSPACE', `320 Manifest 缺少生产工作区：${workspace.key}`)
    continue
  }
  if (entry.title !== workspace.label) {
    fail('WORKSPACE_LABEL_MISMATCH', `${workspace.key} 标题不一致`, {
      production: workspace.label,
      manifest: entry.title
    })
  }
  if (entry.route !== workspace.path) {
    fail('WORKSPACE_ROUTE_MISMATCH', `${workspace.key} 主入口不一致`, {
      production: workspace.path,
      manifest: entry.route
    })
  }

  const productionRoutes = new Set(workspace.children.map((child) => child.path))
  const declaredRoutes = new Set(Array.isArray(entry.coveredRoutes) ? entry.coveredRoutes : [])
  if (!sameSet(productionRoutes, declaredRoutes)) {
    fail('COVERED_ROUTE_MISMATCH', `${workspace.key} coveredRoutes 与生产叶子不一致`, {
      missing: sorted([...productionRoutes].filter((route) => !declaredRoutes.has(route))),
      stale: sorted([...declaredRoutes].filter((route) => !productionRoutes.has(route)))
    })
  }

  const productionPermissions = new Set(workspace.children.map((child) => child.permissionKey).filter(Boolean))
  if (workspace.permissionKey) productionPermissions.add(workspace.permissionKey)
  const declaredPermissions = new Set(Array.isArray(entry.permissionCandidates) ? entry.permissionCandidates : [])
  const missingPermissions = sorted([...productionPermissions].filter((permission) => !declaredPermissions.has(permission)))
  if (missingPermissions.length) {
    fail('PERMISSION_COVERAGE', `${workspace.key} 缺少生产权限候选`, { missingPermissions })
  }

  if (!Array.isArray(entry.states) || !entry.states.length) {
    fail('MISSING_STATES', `${workspace.key} 没有状态契约`)
  }
  if (!Array.isArray(entry.fields) || !entry.fields.length) {
    fail('MISSING_FIELDS', `${workspace.key} 没有字段契约`)
  }
  if (!entry.boundary || typeof entry.boundary !== 'string') {
    fail('MISSING_BOUNDARY', `${workspace.key} 没有业务边界`)
  }
}

for (const key of manifestByKey.keys()) {
  if (!productionByKey.has(key)) {
    fail('STALE_MANIFEST_WORKSPACE', `320 Manifest 含过时工作区：${key}`)
  }
}

const declaredShared = new Map()
for (const item of Array.isArray(manifest?.sharedProductionUrls) ? manifest.sharedProductionUrls : []) {
  if (!item?.route) {
    fail('SHARED_ENTRY_WITHOUT_ROUTE', 'sharedProductionUrls 条目缺少 route', { item })
    continue
  }
  declaredShared.set(item.route, new Set(Array.isArray(item.owners) ? item.owners : []))
}

for (const [route, owners] of sharedUrls) {
  const declaredOwners = declaredShared.get(route)
  if (!declaredOwners) {
    fail('MISSING_SHARED_ROUTE_DECLARATION', `Manifest 未声明共享生产 URL：${route}`, { owners: sorted(owners) })
    continue
  }
  if (!sameSet(owners, declaredOwners)) {
    fail('SHARED_ROUTE_OWNER_MISMATCH', `共享 URL owner 不一致：${route}`, {
      production: sorted(owners),
      manifest: sorted(declaredOwners)
    })
  }
}

for (const route of declaredShared.keys()) {
  if (!sharedUrls.has(route)) {
    fail('STALE_SHARED_ROUTE_DECLARATION', `Manifest 声明了非共享或已过时 URL：${route}`)
  }
}

const report = {
  generatedAt: new Date().toISOString(),
  source: path.relative(REPO_ROOT, SOURCE_PATH).split(path.sep).join('/'),
  manifest: path.relative(REPO_ROOT, MANIFEST_PATH).split(path.sep).join('/'),
  counts: {
    productionWorkspaces: workspaces.length,
    productionLeaves: productionLeaves.length,
    productionUniqueUrls: urlOwners.size,
    productionSharedUrls: sharedUrls.size,
    manifestEntries: entries.length,
    manifestHtmlFiles: htmlOwners.size,
    errors: errors.length,
    notes: notes.length
  },
  sharedUrls: [...sharedUrls].map(([route, owners]) => ({ route, owners: sorted(owners) })),
  errors,
  notes
}

if (!errors.length) {
  note('GRADUATION_PROJECTION_PASS', '毕业设计 8 工作区 / 50 叶子 / 48 URL / 2 共享 URL 投影一致')
  report.notes = notes
  report.counts.notes = notes.length
}

if (reportPath) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true })
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
}

console.log(JSON.stringify(report.counts, null, 2))
for (const item of errors) console.error(`ERROR [${item.code}] ${item.message}`)
for (const item of notes) console.log(`NOTE  [${item.code}] ${item.message}`)

if (errors.length) process.exit(1)
