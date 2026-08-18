import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const urlFor = (path) => new URL(`../../${path}`, import.meta.url)
const read = (path) => fs.readFileSync(urlFor(path), 'utf8')

test('A-C1 backend resolver and public current facade are the single current-term contract', () => {
  const resolver = read('backend/app/modules/academic_affairs/services/academic_affairs_term_context_service.py')
  const facade = read('backend/app/modules/academic_affairs/services/academic_affairs_dashboard_scope_facade.py')

  assert.match(resolver, /calendar\.resolve_current\(/)
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
})

test('reachable current-changing A-W1 pages do not expose a SYS-12 bypass', () => {
  const currentPage = read('frontend/src/modules/academicAffairs/views/AaTermCurrentView.vue')
  const listPage = read('frontend/src/modules/academicAffairs/views/AaTermListView.vue')
  const calendarPage = read('frontend/src/modules/academicAffairs/views/AaCalendarView.vue')

  assert.match(currentPage, /current\?\.currentAuthority === 'CALENDAR_GOVERNANCE'/)
  assert.match(currentPage, /!isResolvedCurrent\(t\) && directSwitchAllowed/)
  assert.match(currentPage, /!isResolvedCurrent\(t\) && governanceManaged/)
  assert.match(currentPage, /\/admin\/system\/academic-calendar/)
  assert.match(currentPage, /currentError/)

  assert.match(listPage, /academicAffairsApi\.getCurrentTerm\(\)/)
  assert.match(listPage, /isResolvedCurrent\(row\)/)
  assert.match(listPage, /currentContext\?\.canDirectSwitch !== false/)
  assert.match(listPage, /governanceManaged/)
  assert.match(listPage, /统一治理切换/)
  assert.match(listPage, /历史学期列表始终可读/)
  assert.doesNotMatch(listPage, /v-if="row\.isCurrent"/)
  assert.doesNotMatch(listPage, /v-else-if="!row\.isCurrent"/)

  assert.match(calendarPage, /academicAffairsApi\.getCurrentTerm\(\)/)
  assert.match(calendarPage, /currentContext\?\.currentAuthority === 'CALENDAR_GOVERNANCE'/)
  assert.match(calendarPage, /isSelectedResolvedCurrent/)
  assert.match(calendarPage, /if \(this\.governanceManaged\) return this\.isSelectedResolvedCurrent/)
  assert.match(calendarPage, /publishCalendar\(this\.termId\)/)
  assert.match(calendarPage, /发布已 fail-closed/)
  assert.doesNotMatch(calendarPage, /t\.isCurrent \? '（当前）'/)
})

test('reachable A-W1 readers resolve current separately while keeping history browsable', () => {
  const weeks = read('frontend/src/modules/academicAffairs/views/AaTermWeeksView.vue')
  const teachingWeeks = read('frontend/src/modules/academicAffairs/views/AaTeachingWeekConfigView.vue')
  const status = read('frontend/src/modules/academicAffairs/views/AaTermStatusView.vue')
  const years = read('frontend/src/modules/academicAffairs/views/AaAcademicYearView.vue')

  for (const source of [weeks, teachingWeeks, status, years]) {
    assert.match(source, /academicAffairsApi\.getCurrentTerm\(\)/)
    assert.match(source, /currentError/)
  }

  assert.match(weeks, /isResolvedCurrent\(t\)/)
  assert.doesNotMatch(weeks, /find\(\(t\) => t\.isCurrent\)/)

  assert.match(teachingWeeks, /isResolvedCurrent\(t\)/)
  assert.doesNotMatch(teachingWeeks, /find\(\(t\) => t\.isCurrent\)/)

  assert.match(status, /isResolvedCurrent\(row\)/)
  assert.doesNotMatch(status, /v-if="row\.isCurrent"/)

  assert.match(years, /isResolvedCurrentYear\(row\)/)
  assert.match(years, /currentContext\?\.yearCode/)
  assert.doesNotMatch(years, /v-if="row\.isCurrentYear"/)
})

test('the current-term real-click Gold matches rows by the label the page actually renders', () => {
  const gold = read('e2e/specs/academic-affairs-current-term-authority.spec.mjs')
  assert.match(gold, /function renderedTermLabel\(term\)/)
  assert.match(gold, /hasText: renderedTermLabel\(term\)/)
  assert.doesNotMatch(gold, /function termRow\(page, termName\)/)
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
