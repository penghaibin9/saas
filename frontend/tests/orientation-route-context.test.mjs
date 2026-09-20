import test from 'node:test'
import assert from 'node:assert/strict'
import { orientationDestination } from '../src/modules/orientation/routeContext.js'

const route = { path: '/admin/orientation/batches', query: { batchId: '9007199254740993', panel: 'students' } }
test('batch workspace navigation retains only its batch, not its local panel', () => {
  assert.equal(orientationDestination('/admin/orientation/verify', route), '/admin/orientation/verify?batchId=9007199254740993')
  assert.equal(orientationDestination('/admin/orientation/data?stage=ADMITTED', route), '/admin/orientation/data?stage=ADMITTED&batchId=9007199254740993')
})
test('explicit destinations, other domains and configuration pages do not inherit stale context', () => {
  assert.equal(orientationDestination('/admin/orientation/verify?batchId=2', route), '/admin/orientation/verify?batchId=2')
  for (const target of ['/admin/orientation/batches', '/admin/orientation/flow-config', '/admin/orientation/checkin', '/admin/student-affairs/leave']) {
    assert.equal(orientationDestination(target, route), target)
  }
  assert.equal(orientationDestination('/admin/orientation/verify', {path:'/admin/other',query:{batchId:'2'}}), '/admin/orientation/verify')
})
