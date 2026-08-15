import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const urlFor = (path) => new URL(`../../${path}`, import.meta.url)
const read = (path) => fs.readFileSync(urlFor(path), 'utf8')

test('A-C1 current-term UI follows the backend authority instead of exposing a governance bypass', () => {
  const resolver = read('backend/app/modules/academic_affairs/services/academic_affairs_term_context_service.py')
  const facade = read('backend/app/modules/academic_affairs/services/academic_affairs_dashboard_scope_facade.py')
  const page = read('frontend/src/modules/academicAffairs/views/AaTermCurrentView.vue')

  assert.match(resolver, /authority="CALENDAR_GOVERNANCE"/)
  assert.match(resolver, /can_direct_switch=False/)
  assert.match(resolver, /GOVERNANCE_SWITCH_ROUTE = "\/admin\/system\/academic-calendar"/)
  assert.match(resolver, /authority="AA_TERM_COMPAT"/)
  assert.match(resolver, /can_direct_switch=True/)
  assert.match(resolver, /len\(legacy_rows\) > 1/)
  assert.match(resolver, /禁止随机选择/)

  assert.match(facade, /from \.academic_affairs_term_context_service import resolve_current_term/)
  assert.match(facade, /resolved = resolve_current_term\(/)
  assert.match(facade, /"currentAuthority": resolved\.authority/)
  assert.match(facade, /"canDirectSwitch": resolved\.can_direct_switch/)
  assert.doesNotMatch(facade, /calendar\.resolve_current/)

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
