import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'

const catalog = fs.readFileSync(new URL('../src/modules/system/systemManagementCatalog.js', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/system/system.routes.js', import.meta.url), 'utf8')

test('implementation center exposes eight real menu leaves and routes', () => {
  assert.equal((catalog.match(/key: 'sys-implementation',/g) || []).length, 1)
  const leaves = [
    'sys-implementation-overview', 'sys-implementation-wizard', 'sys-implementation-presets',
    'sys-implementation-standards',
    'sys-implementation-mapping', 'sys-implementation-installed', 'sys-implementation-changes',
    'sys-implementation-acceptance'
  ]
  for (const key of leaves) assert.match(catalog, new RegExp(key))

  const pageKeys = ['overview', 'wizard', 'presets', 'standards', 'data-mapping', 'installed', 'changes', 'acceptance']
  for (const key of pageKeys) assert.match(routes, new RegExp(`implementation/${key}`))
  assert.equal((routes.match(/SystemImplementationView\.vue/g) || []).length, 7)
  assert.equal((routes.match(/NationalStandardsView\.vue/g) || []).length, 1)
})

test('all implementation routes have backend permission keys', () => {
  const permissionMatches = routes.match(/systemAdmin\.implementation\.[a-z.]+/g) || []
  assert.equal(new Set(permissionMatches).size >= 7, true)
})

