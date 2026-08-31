import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { buildNavigationSurfaceContract } from '../../scripts/generate-navigation-surface-contract.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const contract = JSON.parse(fs.readFileSync(path.join(root, 'shared/contracts/navigation-surface-contract.json'), 'utf8'))
const baseCatalog = JSON.parse(fs.readFileSync(path.join(root, 'shared/contracts/permission-catalog.json'), 'utf8'))
const concreteCatalog = JSON.parse(fs.readFileSync(path.join(root, 'shared/contracts/permission-catalog-b8-concrete.json'), 'utf8'))
const compatibilityCatalog = JSON.parse(fs.readFileSync(path.join(root, 'shared/contracts/permission-catalog-b8-compatibility.json'), 'utf8'))
const catalogCodes = new Set([
  ...baseCatalog.entries.map((item) => item.permissionCode),
  ...concreteCatalog.entries,
  ...compatibilityCatalog.entries
])

test('checked-in navigation surface contract exactly matches generated authority', () => {
  assert.deepEqual(contract, buildNavigationSurfaceContract())
})

test('production visible surfaces have real paths and never expose planned entries', () => {
  const visible = contract.surfaces.filter((item) => !item.hidden && !item.disabled && ['implemented', 'partial'].includes(item.status))
  assert.ok(visible.length > 0)
  assert.deepEqual(visible.filter((item) => !item.path), [])
  assert.deepEqual(visible.filter((item) => item.status === 'planned'), [])
})

test('school and platform navigation permission planes stay separated', () => {
  const school = contract.surfaces.filter((item) => !item.platformOnly)
  const platform = contract.surfaces.filter((item) => item.platformOnly)
  assert.deepEqual(school.flatMap((item) => item.permissionCodes).filter((code) => code.startsWith('platform.')), [])
  assert.deepEqual(platform.flatMap((item) => item.permissionCodes).filter((code) => !code.startsWith('platform.')), [])
})

test('every production navigation permission resolves to the Permission Catalog', () => {
  const production = contract.surfaces.filter(
    (item) => !item.hidden && !item.disabled && ['implemented', 'partial'].includes(item.status)
  )
  const missing = [...new Set(production.flatMap((item) => item.permissionCodes).filter((code) => !catalogCodes.has(code)))].sort()
  assert.deepEqual(missing, [])
})

test('Product IAM and School IAM are explicit production surfaces', () => {
  const byPath = new Map(contract.surfaces.map((item) => [item.path, item]))
  assert.equal(byPath.get('/admin/platform/product-iam')?.permissionKey, 'platform.productIam.view')
  assert.equal(byPath.get('/admin/system/iam')?.permissionKey, 'systemAdmin.role.view')
  assert.equal(byPath.get('/admin/system/iam?surface=templates')?.permissionKey, 'systemAdmin.role.template.view')
  assert.equal(byPath.get('/admin/system/iam?surface=permissions')?.permissionKey, 'systemAdmin.role.permission.manage')
})
