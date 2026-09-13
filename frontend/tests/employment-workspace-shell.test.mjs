import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { workspaceRouteOwner } from '../src/components/workspace/workspaceRouting.js'

const layout = readFileSync(new URL('../src/views/admin/employment/AdminEmploymentLayout.vue', import.meta.url), 'utf8')

test('employment uses the shared workspace shell from its first render', () => {
  assert.match(layout, /<BasePortalLayout[\s\S]*\bworkspace\b/)
  assert.match(layout, /hide-global-workbench/)
  assert.match(layout, /:ctx="ctx"/)
  assert.doesNotMatch(layout, /const MENUS/)
})

test('employment entered from internship stays owned by the internship workspace', () => {
  for (const ref of [
    '/admin/employment/students?source=internship',
    '/admin/employment/students/6400',
    '/admin/employment/materials',
    '/admin/employment/followups'
  ]) {
    const url = new URL(ref, 'http://workspace.local')
    const owner = workspaceRouteOwner(url.pathname, url.pathname + url.search)
    assert.equal(owner.groupKey, 'internship', ref)
    assert.equal(owner.modKey, 'in-employment-archive-stats', ref)
  }

  const unemployed = workspaceRouteOwner('/admin/employment/unemployed', '/admin/employment/unemployed')
  assert.equal(unemployed.groupKey, 'internship')
  assert.equal(unemployed.leafKey, '未就业帮扶')
})
