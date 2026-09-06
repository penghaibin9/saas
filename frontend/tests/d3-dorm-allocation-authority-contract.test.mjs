import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const api = read('../src/modules/studentAffairs/api/studentAffairs.api.js')
const routes = read('../src/modules/studentAffairs/studentAffairs.routes.js')
const allocation = read('../src/modules/studentAffairs/views/dorm/DormAllocationView.vue')
const checkin = read('../src/modules/studentAffairs/views/dorm/DormCheckinView.vue')

test('D3 exposes one allocation-plan workspace with dry-run, manual assignment, publish and conflict export', () => {
  assert.match(routes, /path: 'dorm\/allocation'/)
  assert.match(routes, /permissionKey: 'studentAffairs\.dorm\.view'/)
  for (const suffix of ['', '/dry-run', '/manual-assign', '/publish', '/conflicts.xlsx']) {
    assert.match(api, new RegExp(`dorm/allocation-batches[^\n]*${suffix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
  }
  assert.match(allocation, /发布后学生范围与精确床位资源池将冻结/)
  assert.match(allocation, /Dry Run/)
  assert.match(allocation, /下载异常行\.xlsx/)
})

test('D3 separates allocation from formal check-in and retires the legacy global switch UI', () => {
  assert.match(checkin, /dorm\/allocation/)
  assert.doesNotMatch(checkin, /isSelfSelectEnabled|updateDormConfig|开启学生自选|关闭学生自选/)
  assert.match(allocation, /RESERVED/)
  assert.doesNotMatch(allocation, /Math\.random|\bmock\b|setTimeout\s*\(/i)
})
