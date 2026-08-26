import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const src = (path) => readFileSync(resolve(here, '..', path), 'utf8')

const routes = src('src/modules/graduation/routes.js')
const workspaces = src('src/modules/graduation/config/graduationWorkspaces.js')
const view = src('src/modules/graduation/views/GraduationRiskArchiveView.vue')

for (const source of [routes, workspaces, view]) {
  test('risk/archive UI does not use retired graduation permission aliases', () => {
    assert.doesNotMatch(source, /graduationDesign\.stats\.view/)
    assert.doesNotMatch(source, /graduationDesign\.riskArchive\.manage/)
  })
}

test('stats routes and panel use the backend canonical dashboard permission', () => {
  assert.match(routes, /stats-report[\s\S]*permissionKey:\s*'graduationDesign\.dashboard\.view'/)
  assert.match(routes, /risk-archive[\s\S]*permissionAny:[^\]]*'graduationDesign\.dashboard\.view'/)
  assert.match(view, /canStatsView\(\)[^{]*\{[^}]*graduationDesign\.dashboard\.view/)
})

test('risk/archive workspace leaves use split canonical read permissions', () => {
  assert.match(workspaces, /panel=risk'[^\n]*permissionKey:\s*'graduationDesign\.risk\.view'/)
  assert.match(workspaces, /panel=archive'[^\n]*permissionKey:\s*'graduationDesign\.archive\.view'/)
})
