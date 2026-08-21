import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const LARGE_PDF_BYTES = 30 * 1024 * 1024

test.describe.serial('毕业设计：学生—导师—管理员真实点击闭环 + Viewer 长文档验收', () => {
  let fixture
  const firstRejectReason = '请补充真实测试范围、异常场景和阶段进度说明'
  const secondRejectReason = '请补充长文档阅读验证与最终进度安排后再次提交'

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('学生签署任务书并提交 3 页 synthetic 开题报告', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.open()
    await graduation.signTaskbookIfNeeded()
    await graduation.submitProposal({ suffix: `${fixture.runId}-p3`, fileName: `proposal-3p-${fixture.runId}.pdf`, pages: 3 })
  })

  test('导师用 PDF.js 站内读取 3 页版本并驳回', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('PENDING_REVIEW')
    await graduation.selectStudent(3)
    await graduation.reject(firstRejectReason)
  })

  test('学生看到第一次驳回后重交 60 页 synthetic PDF', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.open()
    await graduation.expectRejected(firstRejectReason)
    await graduation.submitProposal({ suffix: `${fixture.runId}-p60`, fileName: `proposal-60p-${fixture.runId}.pdf`, pages: 60 })
  })

  test('导师验证 60 页 lazy render 后再次驳回', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('PENDING_REVIEW')
    await graduation.selectStudent(60)
    await graduation.reject(secondRejectReason)
  })

  test('学生看到第二次驳回后重交 121 页 / 30MB synthetic PDF', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.open()
    await graduation.expectRejected(secondRejectReason)
    await graduation.submitProposal({
      suffix: `${fixture.runId}-p121-30mb`,
      fileName: `proposal-121p-30mb-${fixture.runId}.pdf`,
      pages: 121,
      targetBytes: LARGE_PDF_BYTES
    })
  })

  test('导师验证 121 页 / 30MB 按需渲染并通过最新版本', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('PENDING_REVIEW')
    await graduation.selectStudent(121)
    await graduation.approve()
  })

  test('学校管理员复核已通过状态与审批留痕', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

    const graduation = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await graduation.openProposals('APPROVED')
    await graduation.selectStudent(121)
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
