import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

test.describe.serial('毕业设计：学生—导师—管理员真实点击闭环', () => {
  let fixture
  const rejectReason = '请补充真实测试范围、异常场景和阶段进度说明'

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('学生签署任务书并提交开题报告', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.open()
    await graduation.signTaskbookIfNeeded()
    await graduation.submitProposal({ suffix: fixture.runId, fileName: `proposal-${fixture.runId}.pdf` })
  })

  test('导师从待审队列打开学生材料并驳回', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('PENDING_REVIEW')
    await graduation.selectStudent()
    await graduation.reject(rejectReason)
  })

  test('学生看到驳回原因后修改并重新提交', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.open()
    await graduation.expectRejected(rejectReason)
    await graduation.submitProposal({ suffix: `${fixture.runId}-resubmit`, fileName: `proposal-resubmit-${fixture.runId}.pdf` })
  })

  test('导师通过新版本', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('PENDING_REVIEW')
    await graduation.selectStudent()
    await graduation.approve()
  })

  test('学校管理员复核已通过状态与审批留痕', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('APPROVED')
    await graduation.selectStudent()
    await graduation.verifyAdminAudit()
    expect(fixture.batchId).not.toBe('')
  })

  test('学生端最终状态同步为已通过', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.open()
    await graduation.expectApproved()
  })
})
