import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const urlFor = (path) => new URL(`../../${path}`, import.meta.url)
const read = (path) => fs.readFileSync(urlFor(path), 'utf8')

test('A-C1 current-term UI follows the backend authority instead of exposing a governance bypass', () => {
  const backend = read('backend/app/modules/academic_affairs/services/academic_affairs_dashboard_scope_facade.py')
  const page = read('frontend/src/modules/academicAffairs/views/AaTermCurrentView.vue')

  assert.match(backend, /"currentAuthority": "CALENDAR_GOVERNANCE"/)
  assert.match(backend, /"canDirectSwitch": False/)
  assert.match(backend, /"switchRoute": "\/admin\/system\/academic-calendar"/)
  assert.match(backend, /"currentAuthority": "AA_TERM_COMPAT"/)
  assert.match(backend, /"canDirectSwitch": True/)

  assert.match(page, /current\?\.currentAuthority === 'CALENDAR_GOVERNANCE'/)
  assert.match(page, /!isResolvedCurrent\(t\) && directSwitchAllowed/)
  assert.match(page, /!isResolvedCurrent\(t\) && governanceManaged/)
  assert.match(page, /\/admin\/system\/academic-calendar/)
  assert.match(page, /currentError/)
  assert.doesNotMatch(page, /this\.current = res\.code === 0 \? res\.data : null/)
})

test('formal teaching-task setup never teaches an 18-week default', () => {
  const termForm = read('frontend/src/modules/academicAffairs/views/AaTermFormView.vue')
  const taskPage = read('frontend/src/modules/academicAffairs/views/AaTaskBatchListView.vue')
  const generator = read('backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py')

  assert.doesNotMatch(termForm, /placeholder="如 18"/)
  assert.match(termForm, /如 17 或 20/)
  assert.match(termForm, /正式教学任务不会默认18周/)
  assert.match(taskPage, /不会猜测生成/)
  assert.doesNotMatch(generator, /_FALLBACK_WEEKS/)
  assert.match(generator, /TEACHING_WEEKS_UNRESOLVED/)
  assert.match(generator, /DATA_CONFLICT/)
})
