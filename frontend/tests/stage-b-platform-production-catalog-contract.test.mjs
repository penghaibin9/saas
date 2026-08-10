import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const catalog = fs.readFileSync(new URL('../src/modules/platform/platformManagementCatalog.js', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/platform/platform.routes.js', import.meta.url), 'utf8')

const retired = [
  'tenant-lifecycle',
  'tenant-transitions',
  'tenant-contacts',
  'products',
  'init-templates',
  'role-templates',
  'releases',
  'support-tickets',
  'support-sessions',
  'tenant-health'
]

test('P1-09 roadmap and production platform catalogs are separated', () => {
  assert.match(catalog, /PLATFORM_MANAGEMENT_ROADMAP_CATALOG/)
  assert.match(catalog, /group\.items\.filter\(\(item\) => item\.view !== 'capability'\)/)
  assert.match(catalog, /PLATFORM_CAPABILITY_ONLY_KEYS/)
})

test('P1-09 production platform routes no longer render PlatformCapabilityView', () => {
  assert.doesNotMatch(routes, /PlatformCapabilityView\.vue/)
  for (const path of retired) {
    const escaped = path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const block = new RegExp(`path: '${escaped}'[\\s\\S]{0,360}?redirect: '/admin/platform/`)
    assert.match(routes, block, `${path} must remain compatibility redirect only`)
  }
})
