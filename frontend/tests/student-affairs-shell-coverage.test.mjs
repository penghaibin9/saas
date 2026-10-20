import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import { usesStudentAffairsWorkspace, workspaceIdentity, workspaceRouteOwner } from '../src/components/workspace/workspaceRouting.js'
const modules = getVisibleNavPlan({ permissionPatterns: ['*'] }).find(group => group.key === 'student-affairs').children

test('every live student-affairs third-level menu uses the same teacher shell', () => {
  let count = 0
  for (const mod of modules) for (const page of mod.children || []) {
    if (!page.path || page.disabled) continue
    assert.equal(usesStudentAffairsWorkspace(page.path.split('?')[0], page.path), true, `${mod.label} / ${page.label}: ${page.path}`)
    count++
  }
  assert.ok(count > 80, `covered ${count} leaf routes`)
})
test('detail and edit routes inherit the student shell without capturing other centers', () => {
  for (const path of ['/admin/student/123', '/admin/student/123/edit', '/admin/campus-service/classes/123', '/admin/orientation/batches/123', '/admin/student-affairs/risk/123', '/admin/student-affairs/dorm/allocation', '/admin/student-affairs/funding/fee-reductions']) assert.equal(usesStudentAffairsWorkspace(path), true, path)
  assert.equal(workspaceRouteOwner('/admin/student/123/edit').modKey, 'sa-profile')
  assert.equal(workspaceRouteOwner('/admin/student-affairs/dorm/allocation').modKey, 'sa-dorm')
  for (const path of ['/admin/platform', '/admin/student-other', '/admin/academic-affairs/terms', '/admin/internship']) assert.equal(usesStudentAffairsWorkspace(path), false, path)
})
test('same user/context shares shell preferences across modules but never across identities', () => {
  const user = { tenantId: 1, userId: 2, currentRoleCode: 'COUNSELOR', activeContextId: 'c1' }
  const key = workspaceIdentity(user, { ctxKey: 'student-module-key' })
  assert.equal(key, workspaceIdentity(user, { ctxKey: 'workbench-different-key' }))
  for (const change of [{tenantId:2},{userId:3},{currentRoleCode:'SCHOOL_ADMIN'},{activeContextId:'c2'}]) assert.notEqual(key, workspaceIdentity({...user,...change}, {}))
})
test('student-affairs parent has no per-page whitelist and renders original business components', () => {
  const source = readFileSync(new URL('../src/modules/studentAffairs/views/AdminStudentAffairsLayout.vue', import.meta.url), 'utf8')
  assert.match(source, /isCoreWorkspace\(\)\s*\{ return true \}/)
  assert.match(source, /<component :is="Component" :ctx="ctx"/)
  const base = readFileSync(new URL('../src/layouts/BasePortalLayout.vue', import.meta.url), 'utf8')
  assert.match(base, /usesStudentAffairsWorkspace\(this\.\$route\.path, this\.\$route\.fullPath\)/)
})
