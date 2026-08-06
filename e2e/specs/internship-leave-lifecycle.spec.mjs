import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffInternshipLeavePage, StudentInternshipPage } from '../pages/internship.page.mjs'

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

test.describe('岗位实习：学生请假—导师审批—学生销假—管理员核验', () => {
  // This suite intentionally persists one state machine across four visible actors.
  // A retry after a later failure would replay the submit step against an existing
  // pending leave and produce a legitimate 409, so this stateful chain fails once
  // with complete evidence instead of contaminating the diagnosis with a retry.
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let leaveId = ''
  let reason = ''
  const returnNote = '已完成就诊并按时返岗'

  test.beforeAll(async () => {
    fixture = await loadInternshipFixture()
    reason = `Playwright 实习请假 ${fixture.runId}：办理个人事务后返岗`
  })

  test('学生通过门户提交实习请假', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const internship = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await internship.openLeave()
    leaveId = await internship.submitLeave({
      startDate: isoDay(1),
      endDate: isoDay(1),
      reason
    })
    expect(leaveId).not.toBe('')
  })

  test('实习指导教师从请假队列审批通过', async ({ page }) => {
    expect(leaveId, '学生步骤必须先生成请假单').not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const internship = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await internship.approve({ leaveId, reason })
  })

  test('学生在已通过请假单上办理销假', async ({ page }) => {
    expect(leaveId, '导师审批步骤必须保留请假单 ID').not.toBe('')
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const internship = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await internship.returnLeave({ leaveId, reason, note: returnNote })
  })

  test('学校管理员核验最终状态与三段审计留痕', async ({ page }) => {
    expect(leaveId, '学生销假步骤必须保留请假单 ID').not.toBe('')
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const internship = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await internship.verifyFinalAudit({ leaveId, returnNote })
  })
})
