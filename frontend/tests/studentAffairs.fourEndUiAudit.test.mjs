import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('student clients share the complete hardship evidence contract', () => {
  const portal = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  const mini = read('miniapp/src/pages/student/affairs/aid.vue')
  for (const source of [portal, mini]) {
    assert.match(source, /memberCount/)
    assert.match(source, /annualIncome|income/)
    assert.match(source, /debt/)
    assert.match(source, /specialTags/)
    assert.match(source, /10-500/)
  }
})

test('leave UIs reject reversed dates and non-extension dates', () => {
  const portal = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  const mini = read('miniapp/src/pages/student/affairs/leave.vue')
  assert.match(portal, /endTime >= leaveForm\.startTime/)
  assert.match(portal, /newEndTime > fmt\(item\.endTime\)/)
  assert.match(mini, /form\.endTime >= this\.form\.startTime/)
  assert.match(mini, /newEndTime > this\.originalEnd/)
})

test('dynamic activity code preserves six digits including leading zero', () => {
  const source = read('miniapp/src/pages/student/affairs/activity.vue')
  assert.match(source, /type="text" inputmode="numeric" maxlength="6"/)
  assert.match(source, /String\(.*detail.*value/)
  assert.match(source, /\^\\d\{6\}\$/)
  assert.doesNotMatch(source, /type="number"[^>]*class="ac__code-input"/)
})

test('credit claims are required, bounded, decimal-safe and server paginated', () => {
  const portal = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  const mini = read('miniapp/src/pages/student/affairs/activity.vue')
  const pc = read('frontend/src/modules/studentAffairs/views/activity/CreditAppealView.vue')
  for (const source of [portal, mini, pc]) {
    assert.match(source, /9999\.99/)
    assert.match(source, /最多保留2位小数/)
    assert.doesNotMatch(source, /主张数值（选填）/)
  }
  assert.match(pc, /status: this\.activeStatus/)
  assert.match(pc, /page: this\.pagination\.page/)
  assert.match(pc, /@page-change="onPageChange"/)
  assert.match(pc, /确认通过并写入积分台账/)
})

test('dorm approvals expose source and target beds and obey actions', () => {
  const mobile = read('miniapp/src/pages/teacher/dorm-review/index.vue')
  const pc = read('frontend/src/modules/studentAffairs/views/dorm/DormTransferView.vue')
  const student = read('miniapp/src/pages/student/affairs/dorm.vue')
  for (const source of [mobile, pc]) {
    assert.match(source, /fromBedLabel/)
    assert.match(source, /toBedLabel/)
    assert.match(source, /allowedActions/)
    assert.match(source, /确认.*通过调宿/)
  }
  assert.doesNotMatch(pc, /床 #\{\{ row\.toBedId \}\}/)
  assert.match(student, /pendingTransfer/)
  assert.match(student, /不能重复提交/)
  assert.match(student, /确认首次入住/)
})

test('teacher high-risk actions require evidence and confirmation', () => {
  const mental = read('miniapp/src/pages/teacher/affairs/mental/index.vue')
  const mentalPc = read('frontend/src/modules/studentAffairs/views/mental/MentalCrisisView.vue')
  const talk = read('miniapp/src/pages/teacher/affairs/talk/index.vue')
  const leave = read('miniapp/src/pages/teacher/affairs-leave/index.vue')
  const review = read('miniapp/src/pages/teacher/affairs-review/index.vue')
  assert.match(mental, /升级原因/)
  assert.match(mental, /确认升级为危机/)
  assert.match(mental, /确认关闭心理关注/)
  assert.match(mentalPc, /升级依据（5-300字）/)
  assert.match(mentalPc, /message="升级后将生成正式风险中枢记录/)
  assert.match(mentalPc, /allowedActions/)
  assert.doesNotMatch(mentalPc, /升级说明（可空）/)
  assert.doesNotMatch(mentalPc, /description="升级后将自动生成风险中枢记录/)
  assert.match(talk, /followContent\.trim\(\)\.length < 5/)
  assert.match(talk, /确认办结谈话/)
  assert.match(leave, /YYYY-MM-DD HH:mm/)
  assert.match(leave, /不能晚于当前时间/)
  assert.match(review, /allowedActions/)
  assert.match(review, /选择等级并通过/)
  assert.match(review, /确认关闭风险/)
})

test('student failure paths preserve editable content', () => {
  const portal = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  const aid = read('miniapp/src/pages/student/affairs/aid.vue')
  const leave = read('miniapp/src/pages/student/affairs/leave.vue')
  assert.match(portal, /修改已保存，但重新提交失败/)
  assert.match(portal, /return false/)
  assert.match(aid, /修改已保存，但重新提交失败/)
  assert.match(leave, /修改已保存，但重新提交失败/)
})
