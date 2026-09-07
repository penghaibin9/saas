import test from 'node:test'
import assert from 'node:assert/strict'
import { createRouter, createMemoryHistory } from 'vue-router'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'

test('考务打印菜单及考场深链始终匹配教务公共布局并保留权限', () => {
  const router = createRouter({ history: createMemoryHistory(), routes: academicAffairsRoutes })
  for (const target of ['/admin/academic-affairs/exam/print/seating', '/admin/academic-affairs/exam/print/seating?roomId=9007199254740993']) {
    const route = router.resolve(target)
    assert.equal(route.matched.length, 2)
    assert.equal(route.matched[0].path, '/admin/academic-affairs')
    assert.equal(route.name, 'aa-exam-seating-print')
    assert.equal(route.meta.permissionKey, 'academicAffairs.exam.view')
    assert.equal(route.meta.requiresAuth, true)
    if (target.includes('?')) assert.equal(route.query.roomId, '9007199254740993')
  }
})
