import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/pages/teacher/schedule-change/index.vue', import.meta.url), 'utf8')
const reviewPage = readFileSync(new URL('../src/pages/teacher/academic-affairs/schedule-change-review.vue', import.meta.url), 'utf8')
const realApi = readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8')

test('教师小程序调停课提交与撤销均显示业务 ID、结果和下一步', () => {
  for (const contract of [
    'role="status"', 'receipt.changeId', 'receipt.courseName', 'receipt.result', 'receipt.next',
    '调停课申请已提交', '待学院审核', '终审生效后课表与考勤同步更新',
    '调停课申请已撤销', '已撤销并保留记录', '从正式课表重新发起'
  ]) assert.ok(page.includes(contract), `教师移动端回执缺少：${contract}`)
})

test('教师移动端仍执行冲突预检与服务端正式提交', () => {
  assert.ok(page.includes('teacherApi.academicScheduleConflictCheck(this._body())'))
  assert.ok(page.includes('teacherApi.submitAcademicScheduleChange(this._body())'))
  assert.ok(page.includes("code === 'DATA_CONFLICT'"))
})

test('教师课表未选择学期或周次时不发送空查询参数', () => {
  const start = realApi.indexOf('export const teacherAcademicMySchedule')
  const end = realApi.indexOf('export const teacherAcademicScheduleConflictCheck', start)
  const block = realApi.slice(start, end)
  assert.ok(block.includes('...(termId ? { termId } : {})'))
  assert.ok(block.includes('...(week ? { week } : {})'))
  assert.ok(!block.includes("termId: termId || ''"))
  assert.ok(!block.includes("week: week || ''"))
})

test('调停课列表和待审批队列使用服务端分页，不在手机上截断全量记录', () => {
  for (const contract of [
    'teacherApi.getAcademicScheduleChanges(undefined, requestedPage, this.changesPageSize)',
    'changesHasMore', 'load(changePage + 1)'
  ]) assert.ok(page.includes(contract), `我的申请缺少服务端分页：${contract}`)
  for (const contract of [
    'teacherApi.getScheduleChangePending(requestedPage, this.pendingPageSize, this.targetChangeId || undefined)',
    'pendingHasMore', 'load(queuePage + 1)'
  ]) assert.ok(reviewPage.includes(contract), `审批队列缺少服务端分页：${contract}`)
  assert.ok(!reviewPage.includes('this.list.slice(this.queuePage'))
})

test('教师审批携带正式版本号，界面不回显未知英文状态', () => {
  assert.ok(reviewPage.includes('teacherApi.reviewScheduleChange(changeId, action, comment, expectedVersion)'))
  assert.ok(realApi.includes('data: { action, comment, expectedVersion }'))
  assert.ok(reviewPage.includes("'状态待核对'"))
  assert.ok(!page.includes('状态待确认（${s}）'))
})
