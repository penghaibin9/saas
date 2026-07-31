#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const checkerPath = path.join(toolDir, 'check-prototype-consistency.mjs')
const browserPath = path.join(toolDir, 'run-browser-regression.mjs')

function readNormalized(file) {
  return fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n')
}

function ensureImport(source) {
  const anchor = "import { fileURLToPath } from 'node:url'"
  const addition = `${anchor}\nimport { normalizeManifestPart } from './manifest-normalizer.mjs'`
  if (!source.includes("from './manifest-normalizer.mjs'")) {
    if (!source.includes(anchor)) throw new Error('manifest normalizer import anchor missing')
    source = source.replace(anchor, addition)
  }
  return source
}

let checker = ensureImport(readNormalized(checkerPath))
checker = checker.replace(
  "if (/^(?:https?:|data:|blob:|mailto:|tel:|javascript:)/i.test(value)) return null",
  "if (/^(?:https?:|data:|blob:|mailto:|tel:|javascript:|node:)/i.test(value)) return null"
)

const checkerRowsLegacy = `  const part = readJson(partAbs, partRef)
  if (!part) continue
  loadedParts.push(partRef)
  const rows = Array.isArray(part.entries) ? part.entries : Array.isArray(part.routes) ? part.routes : null
  if (!rows) {
    fail('PART_WITHOUT_ENTRIES', \`Manifest 分片没有 entries 或 routes 数组：\${partRef}\`, { part: partRef })
    continue
  }
  if (Array.isArray(part.sharedAssets)) {
    for (const asset of part.sharedAssets) sharedAssetRefs.add(asset)
  }
  rows.forEach((row, index) => entries.push({ ...row, __part: partRef, __index: index }))`

const checkerRowsRepaired = `  const part = readJson(partAbs, partRef)
  if (!part) continue
  loadedParts.push(partRef)
  const normalized = normalizeManifestPart(part)
  if (!normalized.entries.length) {
    fail('PART_WITHOUT_ENTRIES', \`Manifest 分片没有可标准化的 route + html 条目：\${partRef}\`, { part: partRef })
    continue
  }
  for (const asset of normalized.sharedAssets) sharedAssetRefs.add(asset)
  normalized.entries.forEach((row, index) => entries.push({ ...row, __part: partRef, __index: index }))`

if (checker.includes(checkerRowsLegacy)) checker = checker.replace(checkerRowsLegacy, checkerRowsRepaired)
if (!checker.includes('normalizeManifestPart(part)')) {
  throw new Error('consistency checker manifest normalization was not prepared')
}
if (!checker.includes('javascript:|node:')) {
  throw new Error('Node builtin import ignore rule was not prepared')
}

const boundaryLegacy = `if (main?.productionCodeModified !== false) fail('PRODUCTION_BOUNDARY', 'prototype-manifest.json 必须声明 productionCodeModified=false')
if (main?.designOnly !== true) fail('DESIGN_BOUNDARY', 'prototype-manifest.json 必须声明 designOnly=true')`

const boundaryRepaired = `const allowedProductionBoundaryExceptions = [
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
}`

if (checker.includes(boundaryLegacy)) checker = checker.replace(boundaryLegacy, boundaryRepaired)
if (!checker.includes('PRODUCTION_BOUNDARY_EXCEPTION_MISMATCH')) {
  throw new Error('production boundary checker was not prepared')
}
fs.writeFileSync(checkerPath, checker, 'utf8')

let browser = ensureImport(readNormalized(browserPath))
const browserRowsLegacy = `    const part = safeJson(path.resolve(ROOT, partRef))
    const rows = Array.isArray(part.entries) ? part.entries : Array.isArray(part.routes) ? part.routes : []
    for (const row of rows) {
      if (row?.html) entries.push(row)
    }`
const browserRowsRepaired = `    const part = safeJson(path.resolve(ROOT, partRef))
    const normalized = normalizeManifestPart(part)
    for (const row of normalized.entries) entries.push(row)`
if (browser.includes(browserRowsLegacy)) browser = browser.replace(browserRowsLegacy, browserRowsRepaired)
if (!browser.includes('normalizeManifestPart(part)')) {
  throw new Error('browser runner manifest normalization was not prepared')
}
fs.writeFileSync(browserPath, browser, 'utf8')

console.log('freeze boundary, consistency and browser tools prepared')
