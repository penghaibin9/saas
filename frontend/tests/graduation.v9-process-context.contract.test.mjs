import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../src/modules/graduation/api/graduation-student.api.js', import.meta.url), 'utf8')
const view = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationProcessView.vue', import.meta.url), 'utf8')
const guard = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationProcessActionView.vue', import.meta.url), 'utf8')
const base = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationProcessActionBaseView.vue', import.meta.url), 'utf8')

test('U4 process student picker restores 130-student deep links', () => {
  assert.match(api, /const pickerSearch = params\.page == null/)
  assert.match(api, /page: 1, pageSize: 200/)
  assert.match(view, /restoreRouteStudent\(\)/)
  assert.match(view, /String\(student\.id\) === String\(sid\)/)
})

test('U4 action entry and return keep the complete process work context', () => {
  assert.match(guard, /beforeRouteEnter/)
  assert.match(guard, /beforeRouteLeave/)
  assert.match(guard, /fillProcessContext/)
  assert.match(guard, /studentId/)
  assert.ok(guard.includes("'batchId'"))
  assert.ok(guard.includes("'queue'"))
  assert.ok(guard.includes("'source'"))
  assert.match(guard, /from\.name !== 'graduation-process'/)
  assert.match(guard, /name: 'graduation-process'/)
  assert.match(base, /this\.\$router\.push\(this\.backTo\)/)

  assert.match(view, /const PROCESS_CONTEXT_KEYS = \['batchId', 'studentId', 'panel', 'queue', 'source', 'returnTo'\]/)
  assert.match(view, /for \(const key of PROCESS_CONTEXT_KEYS\)/)
  assert.match(view, /query\.panel = this\.tab/)
  assert.match(view, /query\.batchId = String\(this\.batchStore\.selectedBatchId\)/)
  assert.match(view, /query\.studentId = String\(this\.current\.id\)/)
})

test('U4 only loads the current student current tab and rejects stale student responses', () => {
  assert.match(view, /ensureTabData\(\)/)
  assert.match(view, /if \(this\.tab === 'taskbook'\) this\.loadTaskbook\(\)/)
  assert.match(view, /else if \(this\.tab === 'guidance'\) this\.loadGuidance\(\)/)
  assert.match(view, /else if \(this\.tab === 'plan'\) this\.loadPlans\(\)/)
  assert.match(view, /else if \(this\.tab === 'eval'\) this\.loadEvals\(\)/)
  assert.match(view, /else if \(this\.tab === 'midterm'\) this\.loadMidterm\(\)/)
  assert.match(view, /contextToken: 0/)
  assert.match(view, /isCurrentRequest\(\{ studentId, epoch \}\)/)
  assert.match(view, /epoch === this\.contextToken/)
})

test('U4 first fold uses teacher-facing work language instead of engineering copy', () => {
  assert.match(view, /class="gp-context-board"/)
  assert.match(view, /当前办理/)
  assert.match(view, /最近记录/)
  assert.match(view, /当前结论/)
  assert.match(view, /recentFact\(\)/)
  assert.match(view, /gateConclusion\(\)/)
  assert.doesNotMatch(view, /冻结工作上下文|不在浏览器聚合|节点准入/)
})

test('U4 teacher workbench does not impersonate student taskbook or rectification actions', () => {
  assert.match(view, /等待学生在学生端确认任务书/)
  assert.match(view, /等待学生提交整改说明/)
  assert.doesNotMatch(view, /代学生确认/)
  assert.doesNotMatch(view, /doConfirmTaskbook/)
  assert.doesNotMatch(view, /openRectifySubmit/)
})

test('U4 duplicate training-manual tab is removed from the operational workbench', () => {
  assert.doesNotMatch(view, /value: 'workflow'/)
  assert.doesNotMatch(view, /GRADUATION_MANUAL_WORKFLOW|GRADUATION_MANUAL_GATES/)
  assert.doesNotMatch(view, /class="gp-panel gp-workflow"/)
})
