import test from 'node:test'
import assert from 'node:assert/strict'
import { orientationDestination, rememberOrientationBatch, restoreOrientationBatch } from '../src/modules/orientation/routeContext.js'

const route = { path: '/admin/orientation/batches', query: { batchId: '9007199254740993', panel: 'students' } }
test('batch workspace navigation retains only its batch, not its local panel', () => {
  assert.equal(orientationDestination('/admin/orientation/verify', route), '/admin/orientation/verify?batchId=9007199254740993')
  assert.equal(orientationDestination('/admin/orientation/data?stage=ADMITTED', route), '/admin/orientation/data?stage=ADMITTED&batchId=9007199254740993')
})

test('return from housing restores only the same identity batch', () => {
  const values = new Map(), storage = {getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)}
  rememberOrientationBatch(storage,'school-a:teacher:role',route)
  assert.equal(restoreOrientationBatch('/admin/orientation/qualification',storage,'school-a:teacher:role'), '/admin/orientation/qualification?batchId=9007199254740993')
  for(const identity of ['school-b:teacher:role','school-a:teacher:other-role']) assert.equal(restoreOrientationBatch('/admin/orientation/qualification',storage,identity),'/admin/orientation/qualification')
  assert.equal(restoreOrientationBatch('/admin/orientation/qualification?batchId=18',storage,'school-a:teacher:role'), '/admin/orientation/qualification?batchId=18')
  assert.deepEqual([...values.values()],['9007199254740993'])
  rememberOrientationBatch(storage,'school-a:teacher:role',{path:'/admin/orientation',query:{batchId:'19'}})
  assert.equal(restoreOrientationBatch('/admin/orientation/materials?batchId=18',storage,'school-a:teacher:role',true), '/admin/orientation/materials?batchId=19')
  assert.equal(restoreOrientationBatch('/admin/orientation/materials?batchId=18',storage,'school-a:teacher:role'), '/admin/orientation/materials?batchId=18')
  rememberOrientationBatch(storage,'school-a:teacher:role',{path:'/admin/orientation/students',query:{batchId:''}})
  assert.equal(restoreOrientationBatch('/admin/orientation/materials?batchId=18',storage,'school-a:teacher:role',true), '/admin/orientation/materials')
})
test('explicit destinations and other domains do not inherit stale context', () => {
  assert.equal(orientationDestination('/admin/orientation/verify?batchId=2', route), '/admin/orientation/verify?batchId=2')
  for (const target of ['/admin/student-affairs/leave']) {
    assert.equal(orientationDestination(target, route), target)
  }
  assert.equal(orientationDestination('/admin/orientation/verify', {path:'/admin/other',query:{batchId:'2'}}), '/admin/orientation/verify')
})

test('batch survives setup and onsite workspace transitions without propagating student filters', () => {
 for (const path of ['batches','flow-config','checkin-points','checkin','progress','qualification','payment','dorm-preassign']) {
  assert.equal(orientationDestination('/admin/orientation/'+path, route), '/admin/orientation/'+path+'?batchId=9007199254740993')
 }
 assert.equal(orientationDestination('/admin/orientation/students/123', route), '/admin/orientation/students/123?batchId=9007199254740993')
})
