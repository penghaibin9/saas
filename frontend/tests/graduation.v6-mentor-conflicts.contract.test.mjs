import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const [view, backend] = await Promise.all([
  readFile(new URL('../src/modules/graduation/views/GraduationMentorConflictsView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../../backend/app/modules/graduation/services/graduation_release_mentor_stats_hardening.py', import.meta.url), 'utf8')
])

test('V6 mentor conflict page displays exactly the three server conflict groups', () => {
  for (const key of ['overCapacity', 'advancedNoMentor', 'unqualifiedMentor']) {
    assert.ok(view.includes(key), `view missing conflict group ${key}`)
    assert.ok(backend.includes(`"${key}"`), `backend missing canonical conflict group ${key}`)
  }
  assert.match(view, /导师超容量/)
  assert.match(view, /进入指导阶段却无导师/)
  assert.match(view, /学生导师不是“已认证”/)
})

test('V6 conflict page only offers repair deep links and never mutates assignments itself', () => {
  assert.match(view, /name: 'graduation-mentor-detail'/)
  assert.match(view, /name: 'graduation-mentor-assign'/)
  assert.match(view, /source: 'mentor-conflicts'/)
  assert.match(view, /returnTo: this\.currentReturnTo\(\)/)
  assert.ok(!view.includes('assignMentor('), 'conflict page must not auto-assign a mentor')
  assert.ok(!view.includes('changeMentor('), 'conflict page must not auto-change a mentor')
  assert.ok(!view.includes('batchAssign('), 'conflict page must not auto-run batch assignment')
})

test('V6 conflict reads are latest-wins and preserve safe batch/return context', () => {
  assert.match(view, /loadToken: 0/)
  assert.match(view, /const token = \+\+this\.loadToken/)
  assert.match(view, /if \(token !== this\.loadToken\) return false/)
  assert.match(view, /batchId: this\.batchStore\.selectedBatchId/)
  assert.match(view, /value\.startsWith\('\/admin\/graduation\/'\)/)
  assert.match(view, /returnTo: this\.safeReturnTo/)
})

test('V6 tells the truth that conflict detection is data-scope wide until backend adds batch filtering', () => {
  assert.match(view, /检测接口当前按角色数据范围返回，不支持 batchId 服务端过滤/)
  assert.match(view, /不在浏览器端抓全量数据伪造批次统计/)
  assert.match(backend, /def detect_assignment_conflicts\(\):/)
  assert.ok(!backend.includes('def detect_assignment_conflicts(batch_id'), 'backend currently has no batch-aware conflict contract')
})
