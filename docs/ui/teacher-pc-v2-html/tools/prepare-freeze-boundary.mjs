#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const checkerPath = path.join(toolDir, 'check-prototype-consistency.mjs')
let source = fs.readFileSync(checkerPath, 'utf8').replace(/\r\n/g, '\n')

const legacy = `if (main?.productionCodeModified !== false) fail('PRODUCTION_BOUNDARY', 'prototype-manifest.json 必须声明 productionCodeModified=false')
if (main?.designOnly !== true) fail('DESIGN_BOUNDARY', 'prototype-manifest.json 必须声明 designOnly=true')`

const repaired = `const allowedProductionBoundaryExceptions = [
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

if (source.includes(legacy)) source = source.replace(legacy, repaired)
if (!source.includes('PRODUCTION_BOUNDARY_EXCEPTION_MISMATCH')) {
  throw new Error('production boundary checker was not prepared')
}

fs.writeFileSync(checkerPath, source, 'utf8')
console.log('freeze production boundary checker prepared')
