import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadStudentAffairsFixture } from '../lib/student-affairs-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import {
  StaffStudentAffairsLeavePage,
  StudentAffairsPortalPage
} from '../pages/student-affairs.page.mjs'

function localDate(daysFromToday = 0) {
  const date = new Date()
  date.setDate(date.getDate() + daysFromToday)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

test.describe('学工请假生产交互闭环', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let leaveId = ''
  let outsideLeaveId = ''
  let reason = ''
  let outsideReason = ''
  let startDate = ''
  let endDate = ''

  test.beforeAll(async () => {
    fixture = await loadStudentAffairsFixture()
    const runId = String(process.env.GITHUB_RUN_ID || Date.now()).replace(/\D/g, '').slice(-12)
    reason = `Playwright 学工请假交互验证 ${runId}`
    outsideReason = `Playwright 跨班级不可见验证 ${runId}`
    startDate = localDate(1)
    endDate = localDate(1)
  })

  test('学生 PC 请假表单先做交互校验且不产生业务写入', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.assertLeaveFormValidation({ startDate, endDate })
  })

  test('其他行政班学生 PC 真实提交请假作为越权负向样本', async ({ page }) => {
    expect(String(fixture.outsideClassId)).not.toBe(String(fixture.classId))
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.outsideStudent)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    outsideLeaveId = await affairs.submitLeave({
      startDate,
      endDate,
      reason: outsideReason
    })
    expect(outsideLeaveId).not.toBe('')
  })

  test('辅导员 PC 待审队列看不到其他行政班学生请假', async ({ page }) => {
    expect(outsideLeaveId, '前序跨班级学生提交步骤必须返回 leave id').not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.assertOutsideLeaveNotVisible(outsideLeaveId)
  })

  test('学生 PC 真实提交本人行政班普通请假', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    leaveId = await affairs.submitLeave({
      startDate,
      endDate,
      reason
    })
    expect(leaveId).not.toBe('')
  })

  test('辅导员 PC 审批本人负责班级的精确请假单', async ({ page }) => {
    expect(leaveId, '前序学生提交步骤必须返回 leave id').not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.approve(leaveId)
  })

  test('学生 PC 取消销假确认时保持已通过且不产生写入', async ({ page }) => {
    expect(leaveId, '前序学生提交步骤必须返回 leave id').not.toBe('')
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.dismissCancelAndStay({ leaveId })
  })

  test('学生 PC 对已通过请假真实申请销假', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.submitCancel({ leaveId })
  })

  test('辅导员 PC 真实确认销假并关闭请假', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.confirmCancel(leaveId)
  })

  test('学生 PC 同步看到已销假终态且非法操作入口消失', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.verifyClosedAsStudent({ startDate })
  })

  test('学校管理员 PC 核验 CLOSED 终态与四段审批留痕', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.sandboxAdmin)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.verifyFinalAsAdmin(leaveId)
  })
})
