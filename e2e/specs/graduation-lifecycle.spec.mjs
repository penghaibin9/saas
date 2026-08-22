import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const LARGE_PDF_BYTES = 30 * 1024 * 1024

test.describe.serial('毕业设计：W7 消息—反馈—冻结 Reader—整改重交 + Viewer 长文档/并发验收', () => {
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

  test('学生从 W7.6 通知进入 W7.5 反馈，核验冻结版本后重交 60 页 PDF', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const graduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await graduation.openFeedbackFromRejectMessage({ minimumCount: 1 })
    await graduation.expectActionableFeedback(firstRejectReason)
    await graduation.verifyFrozenReviewedReader()
    await graduation.resubmitProposalFromFeedback({
      suffix: `${fixture.runId}-p60`,
      fileName: `proposal-60p-${fixture.runId}.pdf`,
      pages: 60
    })
  })

  test('第二次通知整改到 121页/30MB，新版产生后旧阅读快照审批必须 409', async ({ page, browser }) => {
    test.setTimeout(300_000)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const staleReviewer = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await staleReviewer.openProposals('PENDING_REVIEW')
    await staleReviewer.selectStudent(60)

    const staleDraft = `旧版草稿-${fixture.runId}：这段意见必须在新版明确确认后才能提交。`
    const staleTextarea = page.getByPlaceholder('批注将随批阅结果同步学生端…')
    await expect(staleTextarea).toBeEnabled()
    await staleTextarea.fill(staleDraft)

    const reviewerContext = await browser.newContext()
    const studentContext = await browser.newContext()
    try {
      const reviewerPage = await reviewerContext.newPage()
      await new StaffLoginPage(reviewerPage, config.staffBaseUrl).login(config.mentor)
      const freshReviewer = new StaffGraduationPage(reviewerPage, config.staffBaseUrl, fixture)
      await freshReviewer.openProposals('PENDING_REVIEW')
      await freshReviewer.selectStudent(60)
      await freshReviewer.reject(secondRejectReason)

      const studentPage = await studentContext.newPage()
      await new StudentLoginPage(studentPage, config.studentBaseUrl).login(config.student)
      const studentGraduation = new StudentGraduationPage(studentPage, config.studentBaseUrl)
      await studentGraduation.openFeedbackFromRejectMessage({ minimumCount: 2 })
      await studentGraduation.expectActionableFeedback(secondRejectReason)
      await studentGraduation.verifyFrozenReviewedReader()
      await studentGraduation.resubmitProposalFromFeedback({
        suffix: `${fixture.runId}-p121-30mb`,
        fileName: `proposal-121p-30mb-${fixture.runId}.pdf`,
        pages: 121,
        targetBytes: LARGE_PDF_BYTES
      })

      const staleResponsePromise = page.waitForResponse((response) =>
        response.request().method() === 'POST'
        && response.url().includes('/graduation/proposals/')
        && new URL(response.url()).pathname.endsWith('/review')
      )
      await page.getByRole('button', { name: /通过当前版本/ }).click()
      const staleResponse = await staleResponsePromise
      expect(staleResponse.status(), '旧阅读快照必须被服务端拒绝而不是覆盖新版').toBe(409)

      await staleReviewer.expectDocumentViewer(121)
      const carried = page.getByTestId('proposal-carried-draft')
      await expect(carried).toBeVisible()
      await expect(carried).toContainText('上一版本未提交草稿')
      await expect(carried).toContainText(staleDraft)
      await expect(carried).toContainText('不会自动成为当前版本的有效批阅意见')

      const latestTextarea = page.getByPlaceholder('批注将随批阅结果同步学生端…')
      await expect(latestTextarea).toHaveValue('')
      await page.getByRole('button', { name: '带入到当前版本' }).click()
      await expect(latestTextarea).toHaveValue(staleDraft)
      await expect(page.getByText(/该意见最初记录于旧版本，请确认适用于当前版本后再提交/)).toBeVisible()

      await staleReviewer.approve()
    } finally {
      await reviewerContext.close()
      await studentContext.close()
    }
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
