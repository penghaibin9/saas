import test from 'node:test'
import assert from 'node:assert/strict'
import { ORIENTATION_WORKSPACES, orientationWorkspace } from '../src/modules/orientation/workspaces.js'
import { NAV_PLAN, findActiveInPlan } from '../src/config/navPlan.js'
import { workspacePages, workspaceCurrentPage } from '../src/components/workspace/teacherWorkspace.js'
import { activeWorkspacePage } from '../src/components/workspace/workspaceRouting.js'

test('all existing orientation functions remain reachable in eight task workspaces',()=>{
  const module=NAV_PLAN.find(g=>g.key==='student-affairs').children.find(m=>m.key==='sa-orientation')
  assert.equal(module.children.length,8)
  const paths=ORIENTATION_WORKSPACES.flatMap(g=>g.pages.map(p=>p.path))
  assert.equal(new Set(paths).size,20)
  for(const path of paths){
    const expected=orientationWorkspace(path)
    assert.equal(findActiveInPlan(path).leafKey,expected.label)
    assert.equal(workspaceCurrentPage(workspacePages([module]),path).title,expected.label)
    assert.equal(activeWorkspacePage(workspacePages([module]), {path, fullPath:path+'?batchId=18', query:{batchId:'18'}}, 'sa-orientation').title, expected.label)
  }
})
test('student detail stays in orientation and highlights student handling',()=>{
  const path='/admin/orientation/students/9007199254740993'
  assert.equal(orientationWorkspace(path).label,'新生办理')
  assert.deepEqual(findActiveInPlan(path),{groupKey:'student-affairs',modKey:'sa-orientation',leafKey:'新生办理'})
})
