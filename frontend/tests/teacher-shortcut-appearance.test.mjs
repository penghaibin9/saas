import assert from 'node:assert/strict'
import test from 'node:test'
import { restoreWorkspace, shortcutAppearance, WORKSPACE_TONES } from '../src/components/workspace/teacherWorkspace.js'
const pages = [
  { id:'/admin/approval/todos', path:'/admin/approval/todos', title:'我的待办' },
  { id:'/admin/student-affairs/leave', path:'/admin/student-affairs/leave', title:'请假审批' },
  { id:'/admin/student-affairs/risk', path:'/admin/student-affairs/risk', title:'风险预警' }
]
test('shortcut defaults have distinct icons and filled colors for different businesses', () => {
  assert.equal(shortcutAppearance(pages[0]).color, 'amber')
  assert.equal(shortcutAppearance(pages[1]).icon, 'calendar')
  assert.equal(shortcutAppearance(pages[2]).color, 'coral')
  assert.equal(Object.keys(WORKSPACE_TONES).length, 6)
  assert.deepEqual(restoreWorkspace({}, pages).shortcuts, pages.map(page => page.id))
})
test('saved icon, color, label and order survive reload, with revoked pages removed', () => {
  const saved = { shortcuts:[pages[2].id, '/denied', pages[0].id], appearance:{ [pages[2].id]:{icon:'star',color:'cyan',label:'我的重点'}, '/denied':{icon:'user',color:'coral'} } }
  const restored = restoreWorkspace(saved, pages)
  assert.deepEqual(restored.shortcuts, [pages[2].id,pages[0].id])
  assert.deepEqual(restored.appearance[pages[2].id], {icon:'star',color:'cyan',label:'我的重点'})
  assert.equal(restored.appearance['/denied'], undefined)
  assert.deepEqual(saved.shortcuts, [pages[2].id,'/denied',pages[0].id])
})
test('invalid icon and color fall back safely and empty shortcuts remain empty', () => {
  const restored = restoreWorkspace({ shortcuts:[], appearance:{ [pages[1].id]:{icon:'__proto__',color:'constructor',label:'abcdefghijklmnopqr'} } }, pages)
  assert.deepEqual(restored.shortcuts, [])
  assert.deepEqual(restored.appearance[pages[1].id], {icon:'calendar',color:'sage',label:'abcdefghijklmnop'})
})
