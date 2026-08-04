#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { normalizeManifestPart } from './manifest-normalizer.mjs'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(TOOL_DIR, '..')
const argv = new Set(process.argv.slice(2))
const strict = argv.has('--strict')
const requireScreenshots = argv.has('--require-screenshots')
const reportArg = process.argv.slice(2).find((v) => v.startsWith('--report='))
const reportPath = reportArg ? path.resolve(process.cwd(), reportArg.slice('--report='.length)) : null

const errors = []
const warnings = []
const notes = []

function rel(abs) {
  return path.relative(ROOT, abs).split(path.sep).join('/')
}

function fail(code, message, detail = {}) {
  errors.push({ code, message, ...detail })
}

function warn(code, message, detail = {}) {
  warnings.push({ code, message, ...detail })
}

function readJson(abs, label) {
  try {
    return JSON.parse(fs.readFileSync(abs, 'utf8'))
  } catch (error) {
    fail('INVALID_JSON', `${label} 不是有效 JSON：${error.message}`, { file: rel(abs) })
    return null
  }
}

function walk(abs, out = []) {
  if (!fs.existsSync(abs)) return out
  for (const item of fs.readdirSync(abs, { withFileTypes: true })) {
    const child = path.join(abs, item.name)
    if (item.isDirectory()) walk(child, out)
    else if (item.isFile()) out.push(child)
  }
  return out
}

function insideRoot(abs) {
  const relative = path.relative(ROOT, abs)
  return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)
}

function normalizeAssetRef(raw) {
  const value = String(raw || '').trim()
  if (!value || value.startsWith('#') || value.startsWith('/') || value.startsWith('//')) return null
  if (/^(?:https?:|data:|blob:|mailto:|tel:|javascript:|node:)/i.test(value)) return null
  const clean = value.split('#')[0].split('?')[0]
  if (!clean || clean.startsWith('{') || clean.includes('${')) return null
  try {
    return decodeURIComponent(clean)
  } catch {
    return clean
  }
}

function extractRefs(content, extension) {
  const refs = []
  if (extension === '.html') {
    const attr = /\b(?:src|href|poster)\s*=\s*["']([^"']+)["']/gi
    for (const match of content.matchAll(attr)) refs.push(match[1])
    const srcset = /\bsrcset\s*=\s*["']([^"']+)["']/gi
    for (const match of content.matchAll(srcset)) {
      for (const item of match[1].split(',')) refs.push(item.trim().split(/\s+/)[0])
    }
  }
  if (extension === '.css' || extension === '.html') {
    const cssUrl = /url\(\s*["']?([^"')]+)["']?\s*\)/gi
    for (const match of content.matchAll(cssUrl)) refs.push(match[1])
  }
  if (extension === '.js' || extension === '.mjs') {
    const importRef = /\b(?:import\s*(?:[^'";]+?\s+from\s*)?|export\s+[^'";]+?\s+from\s*)["']([^"']+)["']/g
    for (const match of content.matchAll(importRef)) refs.push(match[1])
  }
  return refs
}

const mainPath = path.join(ROOT, 'prototype-manifest.json')
if (!fs.existsSync(mainPath)) fail('MISSING_MAIN_MANIFEST', '缺少 prototype-manifest.json')
const main = fs.existsSync(mainPath) ? readJson(mainPath, 'prototype-manifest.json') : null
const partRefs = main?.aggregation?.parts
if (!Array.isArray(partRefs) || !partRefs.length) {
  fail('MISSING_PART_LIST', 'prototype-manifest.json 未声明 aggregation.parts')
}

const entries = []
const sharedAssetRefs = new Set()
const loadedParts = []
for (const partRef of Array.isArray(partRefs) ? partRefs : []) {
  const partAbs = path.resolve(ROOT, partRef)
  if (!insideRoot(partAbs)) {
    fail('PART_PATH_ESCAPE', `Manifest 分片越出原型目录：${partRef}`, { part: partRef })
    continue
  }
  if (!fs.existsSync(partAbs)) {
    fail('MISSING_MANIFEST_PART', `Manifest 分片不存在：${partRef}`, { part: partRef })
    continue
  }
  const part = readJson(partAbs, partRef)
  if (!part) continue
  loadedParts.push(partRef)
  const normalized = normalizeManifestPart(part)
  if (!normalized.entries.length) {
    fail('PART_WITHOUT_ENTRIES', `Manifest 分片没有可标准化的 route + html 条目：${partRef}`, { part: partRef })
    continue
  }
  for (const asset of normalized.sharedAssets) sharedAssetRefs.add(asset)
  normalized.entries.forEach((row, index) => entries.push({ ...row, __part: partRef, __index: index }))
}

const routeOwners = new Map()
const duplicateRoutes = []
const htmlOwners = new Map()
const referencedHtml = new Set()
let sharedPrototypeEntries = 0

for (const entry of entries) {
  const label = `${entry.__part}#${entry.__index + 1}`
  if (!entry.route || typeof entry.route !== 'string') fail('ENTRY_WITHOUT_ROUTE', `${label} 缺少 route`, { part: entry.__part, index: entry.__index })
  if (!entry.html || typeof entry.html !== 'string') {
    fail('ENTRY_WITHOUT_HTML', `${label} 缺少 html`, { part: entry.__part, index: entry.__index })
    continue
  }

  const htmlAbs = path.resolve(ROOT, entry.html)
  if (!insideRoot(htmlAbs)) fail('HTML_PATH_ESCAPE', `${label} 的 html 越出原型目录：${entry.html}`, { html: entry.html })
  else if (!fs.existsSync(htmlAbs)) fail('MISSING_HTML', `${label} 引用的 HTML 不存在：${entry.html}`, { html: entry.html, route: entry.route })
  else if (!fs.statSync(htmlAbs).isFile()) fail('HTML_NOT_FILE', `${entry.html} 不是文件`, { html: entry.html })

  referencedHtml.add(entry.html)
  if (!htmlOwners.has(entry.html)) htmlOwners.set(entry.html, [])
  htmlOwners.get(entry.html).push(entry)
  if (entry.sharedPrototype === true) sharedPrototypeEntries += 1

  if (entry.route) {
    if (routeOwners.has(entry.route)) {
      duplicateRoutes.push({ route: entry.route, previous: routeOwners.get(entry.route), current: entry })
    }
    routeOwners.set(entry.route, entry)
  }

  for (const covered of Array.isArray(entry.coveredRoutes) ? entry.coveredRoutes : []) {
    if (typeof covered !== 'string' || !covered.trim()) fail('INVALID_COVERED_ROUTE', `${label} 含无效 coveredRoutes`, { route: entry.route })
  }
}

for (const duplicate of duplicateRoutes) {
  if (duplicate.previous.__part === duplicate.current.__part) {
    fail('DUPLICATE_ROUTE_IN_PART', `同一 Manifest 分片重复 route：${duplicate.route}`, {
      part: duplicate.current.__part,
      firstIndex: duplicate.previous.__index,
      secondIndex: duplicate.current.__index
    })
  } else {
    notes.push({
      code: 'ROUTE_OVERRIDE',
      message: `route 由后加载分片覆盖：${duplicate.route}`,
      previousPart: duplicate.previous.__part,
      currentPart: duplicate.current.__part
    })
  }
}

for (const [html, owners] of htmlOwners) {
  if (owners.length <= 1) continue
  const allMarkedShared = owners.every((entry) => entry.sharedPrototype === true || entry.sharedExistingHtml === true)
  if (!allMarkedShared) {
    warn('UNMARKED_SHARED_HTML', `多个业务切面复用同一 HTML，但并非全部显式标记共享：${html}`, {
      html,
      routes: owners.map((entry) => entry.route)
    })
  }
}

for (const asset of sharedAssetRefs) {
  const abs = path.resolve(ROOT, asset)
  if (!insideRoot(abs)) fail('SHARED_ASSET_PATH_ESCAPE', `sharedAssets 越出原型目录：${asset}`, { asset })
  else if (!fs.existsSync(abs)) fail('MISSING_SHARED_ASSET', `sharedAssets 文件不存在：${asset}`, { asset })
}

const allFiles = walk(ROOT)
const htmlFiles = allFiles.filter((file) => path.extname(file).toLowerCase() === '.html').map(rel).sort()
const sharedFiles = allFiles.filter((file) => rel(file).startsWith('shared/')).map(rel).sort()
const orphanHtml = htmlFiles.filter((file) => !referencedHtml.has(file))
const missingFromDisk = [...referencedHtml].filter((file) => !htmlFiles.includes(file))

for (const file of orphanHtml) fail('ORPHAN_HTML', `HTML 未被任何 Manifest 条目引用：${file}`, { html: file })
for (const file of missingFromDisk) fail('MISSING_REFERENCED_HTML', `Manifest 引用但磁盘不存在：${file}`, { html: file })

const brokenRefs = []
const escapedRefs = []
for (const abs of allFiles) {
  const extension = path.extname(abs).toLowerCase()
  if (!['.html', '.css', '.js', '.mjs'].includes(extension)) continue
  const content = fs.readFileSync(abs, 'utf8')
  for (const rawRef of extractRefs(content, extension)) {
    const refValue = normalizeAssetRef(rawRef)
    if (!refValue) continue
    const target = path.resolve(path.dirname(abs), refValue)
    if (!insideRoot(target)) {
      escapedRefs.push({ source: rel(abs), ref: rawRef })
      continue
    }
    if (!fs.existsSync(target)) brokenRefs.push({ source: rel(abs), ref: rawRef, resolved: rel(target) })
  }
}

for (const item of escapedRefs) fail('RELATIVE_REF_ESCAPE', `${item.source} 的相对资源越出原型目录：${item.ref}`, item)
for (const item of brokenRefs) fail('BROKEN_RELATIVE_REF', `${item.source} 引用不存在的相对资源：${item.ref}`, item)

const screenshotRefs = []
for (const entry of entries) {
  for (const screenshot of Array.isArray(entry.screenshots) ? entry.screenshots : []) {
    screenshotRefs.push({ screenshot, route: entry.route, part: entry.__part })
  }
}
const missingScreenshots = screenshotRefs.filter(({ screenshot }) => !fs.existsSync(path.resolve(ROOT, screenshot)))
if (missingScreenshots.length) {
  const message = `${missingScreenshots.length} 个历史/计划截图路径尚未入库`
  if (requireScreenshots) fail('MISSING_SCREENSHOTS', message, { sample: missingScreenshots.slice(0, 20) })
  else warn('PLANNED_SCREENSHOTS_NOT_COMMITTED', message, { sample: missingScreenshots.slice(0, 10) })
}

const coverage = main?.coverage || {}
const expected = {
  registeredPrototypeEntries: entries.length,
  uniqueHtmlFiles: referencedHtml.size,
  sharedRouteEntries: sharedPrototypeEntries,
  sharedDesignFiles: sharedFiles.length
}
for (const [key, actual] of Object.entries(expected)) {
  if (typeof coverage[key] !== 'number') fail('MISSING_COVERAGE_COUNT', `prototype-manifest.json.coverage.${key} 缺失`, { key, actual })
  else if (coverage[key] !== actual) fail('COVERAGE_COUNT_MISMATCH', `${key} 声明为 ${coverage[key]}，程序统计为 ${actual}`, { key, declared: coverage[key], actual })
}

const allowedProductionBoundaryExceptions = [
  'frontend/src/config/navPlan.js',
  'frontend/src/config/navPlan.permission-contract.test.js',
  'frontend/tests/studentAffairs.permissionCatalog.test.mjs'
]
const declaredProductionBoundaryExceptions = Array.isArray(main?.productionBoundaryExceptions)
  ? [...new Set(main.productionBoundaryExceptions)].sort()
  : []
const expectedProductionBoundaryExceptions = [...allowedProductionBoundaryExceptions].sort()

if (main?.productionCodeModified === true) {
  if (main?.designOnly !== false) {
    fail('DESIGN_BOUNDARY', '存在生产边界例外时 designOnly 必须为 false')
  }
  if (JSON.stringify(declaredProductionBoundaryExceptions) !== JSON.stringify(expectedProductionBoundaryExceptions)) {
    fail('PRODUCTION_BOUNDARY_EXCEPTION_MISMATCH', '生产边界例外必须精确等于冻结允许清单', {
      declared: declaredProductionBoundaryExceptions,
      expected: expectedProductionBoundaryExceptions
    })
  }
} else {
  if (main?.productionCodeModified !== false) {
    fail('PRODUCTION_BOUNDARY', 'productionCodeModified 必须为 true 或 false')
  }
  if (main?.designOnly !== true) {
    fail('DESIGN_BOUNDARY', '无生产边界例外时 designOnly 必须为 true')
  }
  if (declaredProductionBoundaryExceptions.length) {
    fail('UNEXPECTED_PRODUCTION_BOUNDARY_EXCEPTIONS', 'productionCodeModified=false 时不得声明生产边界例外', {
      declared: declaredProductionBoundaryExceptions
    })
  }
}
if (main?.status === 'FROZEN' && (errors.length || (requireScreenshots && missingScreenshots.length))) {
  fail('FALSE_FROZEN_STATUS', '仍有一致性问题或缺失截图时不得标记 FROZEN')
}

const report = {
  generatedAt: new Date().toISOString(),
  root: ROOT,
  mode: { strict, requireScreenshots },
  counts: {
    manifestPartsDeclared: Array.isArray(partRefs) ? partRefs.length : 0,
    manifestPartsLoaded: loadedParts.length,
    registeredPrototypeEntries: entries.length,
    uniqueReferencedHtml: referencedHtml.size,
    actualHtmlFiles: htmlFiles.length,
    sharedPrototypeEntries,
    actualSharedFiles: sharedFiles.length,
    routeOverrides: notes.filter((item) => item.code === 'ROUTE_OVERRIDE').length,
    orphanHtml: orphanHtml.length,
    brokenRelativeRefs: brokenRefs.length,
    escapedRelativeRefs: escapedRefs.length,
    screenshotRefs: screenshotRefs.length,
    missingScreenshots: missingScreenshots.length,
    errors: errors.length,
    warnings: warnings.length
  },
  errors,
  warnings,
  notes,
  orphanHtml,
  brokenRefs,
  escapedRefs
}

if (reportPath) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true })
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
}

console.log(JSON.stringify(report.counts, null, 2))
for (const item of errors) console.error(`ERROR [${item.code}] ${item.message}`)
for (const item of warnings) console.warn(`WARN  [${item.code}] ${item.message}`)
for (const item of notes) console.log(`NOTE  [${item.code}] ${item.message}`)

if (errors.length || (strict && warnings.length)) process.exit(1)
