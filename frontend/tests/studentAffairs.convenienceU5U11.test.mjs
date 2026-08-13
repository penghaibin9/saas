import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('U5 teacher miniapp consumes server due truth and presents priority bands', () => {
  const service = read('backend/app/services/affairs_teacher_workbench_service.py')
  const view = read('miniapp/src/pages/teacher/affairs/index.vue')
  assert.match(service, /prioritySummary/)
  assert.match(service, /dueWithin24h/)
  assert.match(view, /今日先做/)
  assert.match(view, /priorityClass\(item\)/)
  assert.doesNotMatch(view, /priority\s*===\s*['"](HIGH|LOW)/)
})

test('U6 followup workbench keeps continuous queue context', () => {
  const view = read('frontend/src/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue')
  assert.match(view, /if \(!this\.selectedId && this\.rows\.length\) this\.select\(this\.rows\[0\]\.id\)/)
  assert.match(view, /oldIndex/)
  assert.match(view, /处理完自动打开下一条/)
})

test('U7 aid batch defaults the common academic year while keeping formal validation server-side', () => {
  const view = read('frontend/src/modules/studentAffairs/views/AidWorkbenchView.vue')
  assert.match(view, /currentSchoolYear/)
  assert.match(view, /schoolYearOptions/)
  assert.match(view, /sa\.aid\.statement/)
  assert.match(view, /this\.currentSchoolYear/)
})

test('U8 and U9 funding preflight and amount suggestion come from the backend contract', () => {
  const view = read('frontend/src/modules/studentAffairs/views/FundingWorkbenchView.vue')
  const api = read('frontend/src/modules/studentAffairs/api/studentAffairs.api.js')
  const service = read('backend/app/services/affairs_funding_service.py')
  assert.match(api, /funding\/preflight/)
  assert.match(view, /preflightFunding/)
  assert.match(view, /amountPolicy/)
  assert.match(view, /m\.amount == null \? null : m\.amount/)
  assert.doesNotMatch(view, /onApplyStudentChange[\s\S]{0,1200}inDifficultLibrary\s*\?/)
  assert.match(service, /_check_grant\(db, sid, project\)/)
  assert.match(service, /_check_scholarship\(db, sid, project\)/)
  assert.match(service, /_validated_amount/)
  assert.match(service, /submitWillRevalidate/)
})

test('U10 material notice deep-links to one authorized requirement on all consumers', () => {
  const operations = read('backend/app/services/affairs_operations_service.py')
  const registry = read('backend/app/services/message_action_registry.py')
  const view = read('frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue')
  const miniDetail = read('miniapp/src/pages/common/message-detail/index.vue')
  assert.match(operations, /action_key="student\.affairs\.material"/)
  assert.match(registry, /"student\.affairs\.material"/)
  assert.match(registry, /"materialRequirementId"/)
  assert.match(view, /requirementId: this\.focusRequirementId/)
  assert.match(miniDetail, /useSessionStore\(\)\.isTeacher/)
  assert.match(miniDetail, /pages\/teacher\/affairs\/index/)
})

test('U11 dashboard priority rows reuse permission-filtered drill paths', () => {
  const view = read('frontend/src/modules/studentAffairs/views/StudentAffairsDashboardView.vue')
  assert.match(view, /path: card\('pendingTodo'\)\.drillPath/)
  assert.match(view, /path: card\('pendingLeave'\)\.drillPath/)
  assert.match(view, /path: card\('riskStudents'\)\.drillPath/)
  assert.match(view, /@click="go\(item\.path\)"/)
})
