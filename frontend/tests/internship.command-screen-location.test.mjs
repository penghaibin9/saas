import test from 'node:test'
import assert from 'node:assert/strict'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import { withInternshipBatch, internshipBatchSwitch, internshipLocation } from '../src/modules/internship/navigation.js'

const path = '/admin/internship/command-screen'
function menu(permissionPatterns) {
  return getVisibleNavPlan({ permissionPatterns, ctxKey: 'screen-navigation' })
    .find(group => group.key === 'internship')?.children || []
}

test('screen is first second-level menu and requires stats permission', () => {
  const entry = menu(['internship.stats.view'])[0]
  assert.equal(entry.key, 'in-command-screen')
  assert.equal(entry.label, '实习中心大屏')
  assert.equal(entry.children[0].path, path)
  assert.equal(menu(['internship.dashboard.view']).some(item => item.key === entry.key), false)
  assert.equal(menu([]).some(item => item.key === entry.key), false)
})

test('screen entry retains large batch IDs without rounding', () => {
  assert.deepEqual(withInternshipBatch(path, '9007199254740999'), {
    path, query: { batchId: '9007199254740999' }, hash: ''
  })
})

test('switching batch remains on the dedicated screen route', () => {
  const target = internshipBatchSwitch(path + '?batchId=1', '2')
  assert.equal(target.path, path)
  assert.equal(target.query.batchId, '2')
})

test('deep link resolves to the screen menu instead of workbench', () => {
  assert.equal(internshipLocation(path + '?batchId=1').workspaceKey, 'in-command-screen')
})
