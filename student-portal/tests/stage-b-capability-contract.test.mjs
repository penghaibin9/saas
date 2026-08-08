import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PORTAL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(PORTAL_ROOT, '..')

function readPortal(relativePath) {
  return fs.readFileSync(path.join(PORTAL_ROOT, relativePath), 'utf8')
}

function readRepo(relativePath) {
  return fs.readFileSync(path.join(REPO_ROOT, relativePath), 'utf8')
}

test('P1-01 generic module route cannot expose mock fixture or fake future actions', () => {
  const source = readPortal('src/views/template/ModuleTemplateView.vue')
  assert.doesNotMatch(source, /portalTemplateFixture/)
  assert.doesNotMatch(source, /后续版本接入/)
  assert.doesNotMatch(source, /Object\.values\s*\(/)
  assert.doesNotMatch(source, /ui\.notify\s*\(/)
  assert.match(source, /未登记为学生门户正式能力/)
})

test('P1-02 service hall UI is driven by real server catalog without fake counts/hot links', () => {
  const source = readPortal('src/views/hall/ServiceHallView.vue')
  assert.match(source, /portalApi\.serviceHallCatalog\s*\(/)
  assert.doesNotMatch(source, /\bconst\s+HOT\b/)
  assert.doesNotMatch(source, /\bcountOf\s*\(/)
  assert.doesNotMatch(source, /20,\s*graduation:\s*10/)
  assert.match(source, /目录读取失败/)
})

test('server service-hall catalog paths are registered by student portal router', () => {
  const service = readRepo('backend/app/student_portal/services/service_hall_service.py')
  const router = readPortal('src/router/index.js')
  const tuplePattern = /\("[^"]+",\s*"[^"]+",\s*"([^"]+)"\)/g
  const paths = [...service.matchAll(tuplePattern)].map((match) => match[1])
  assert.ok(paths.length >= 5, 'expected real service hall catalog entries')
  for (const routePath of paths) {
    assert.match(router, new RegExp(`path:\\s*['"]${routePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}['"]`), `catalog path ${routePath} must exist in router`)
  }
})
