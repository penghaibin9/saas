import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffInternshipLeavePage, StudentInternshipPage } from '../pages/internship.page.mjs'

const PREFIX = 'E2E-AUDIT-20260823'

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function parseResponse(response) {
  const text = await response.text()
  try { return { text, body: JSON.parse(text) } } catch { return { text, body: null } }
}

test.describe('岗位实习审计：请假驳回—反馈可见—重交—再审批—销假', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let rejectedLeaveId = ''
  let resubmittedLeaveId = ''
  let firstReason = ''
  let resubmitReason = ''
  let rejectReason = ''
  const returnNote = `${PREFIX}-销假-已返岗`
  const startDate = isoDay(2)
  const endDate = isoDay(2)

  test.beforeAll(async () => {
    fixture = await loadInternshipFixture()
    firstReason = `${PREFIX}-${fixture.runId}-请假-初次提交`
    resubmitReason = `${PREFIX}-${fixture.runId}-请假-整改重交`
    rejectReason = `${PREFIX}-驳回-请补充返岗安排后重交`
  })

  test('学生真实提交，重复提交被 fail-closed，刷新后数据仍在', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const internship = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await internship.openLeave()
    rejectedLeaveId = await internship.submitLeave({ startDate, endDate, reason: firstReason })
    expect(rejectedLeaveId).not.toBe('')

    const form = internship.leaveForm()
    const duplicateReason = `${PREFIX}-${fixture.runId}-重复提交应拒绝`
    await form.locator('textarea').fill(duplicateReason)
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith('/api/v1/portal/internship/context/leaves')
      && response.request().method() === 'POST'
    )
    await form.getByRole('button', { name: '提交请假' }).click()
    const response = await responsePromise
    const { text, body } = await parseResponse(response)
    const businessSucceeded = response.ok() && (!body || body.code === 0)
    expect(businessSucceeded, `重复提交不应成功: ${text.slice(0, 800)}`).toBeFalsy()
    await expect(page.getByText(/待审批的请假申请|先等待处理或撤回|请假提交失败/).first()).toBeVisible()

    await page.reload()
    await expect(page.getByRole('button', { name: '实习请假' })).toBeVisible()
    await page.getByRole('button', { name: '实习请假' }).click()
    const persisted = internship.leaveRow(firstReason)
    await expect(persisted).toBeVisible()
    await expect(persisted).toContainText(/待审批|PENDING/)
    await expect(internship.leaveRow(duplicateReason)).toHaveCount(0)
  })

  test('Tenant B 直接打开 Tenant A 请假详情 URL 不得看到数据', async ({ page }) => {
    expect(rejectedLeaveId).not.toBe('')
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.demoAdmin)

    const detailPath = `/api/v1/internship/leaves/${rejectedLeaveId}`
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === detailPath && response.request().method() === 'GET',
      { timeout: 20_000 }
    ).catch(() => null)

    const query = new URLSearchParams({
      batchId: fixture.batchId,
      panel: 'all',
      id: rejectedLeaveId
    })
    await page.goto(`${config.staffBaseUrl}/admin/internship/leaves?${query}`)
    const response = await responsePromise

    if (response) {
      const { text, body } = await parseResponse(response)
      const leaked = response.ok() && body?.code === 0
        && String(body?.data?.id || '') === String(rejectedLeaveId)
      expect(leaked, `跨租户详情泄漏: ${text.slice(0, 800)}`).toBeFalsy()
    }
    await expect(page.getByText(firstReason, { exact: false })).toHaveCount(0)
  })

  test('实习导师真实驳回并写入审批意见', async ({ page }) => {
    expect(rejectedLeaveId).not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const internship = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await internship.openPending()
    await internship.selectLeave(rejectedLeaveId)
    const detail = page.locator('.lv-main')
    await expect(detail).toContainText(firstReason)

    const rejectButton = page.locator('.lv-foot').getByRole('button', { name: '驳回' })
    await expect(rejectButton).toBeEnabled()
    await rejectButton.click()

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('请假 · 驳回')
    await dialog.locator('textarea').fill(rejectReason)
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/leaves/${rejectedLeaveId}/review`)
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '驳回' }).click()
    const response = await responsePromise
    const { text, body } = await parseResponse(response)
    expect(response.ok(), text.slice(0, 800)).toBeTruthy()
    expect(body?.code).toBe(0)
    expect(body?.data?.status).toBe('REJECTED')
  })

  test('学生刷新后看到驳回原因，并从浏览器重新提交整改单', async ({ page }) => {
    expect(rejectedLeaveId).not.toBe('')
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const internship = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await internship.openLeave()

    await page.reload()
    await expect(page.getByRole('button', { name: '实习请假' })).toBeVisible()
    await page.getByRole('button', { name: '实习请假' }).click()

    const rejectedRow = internship.leaveRow(firstReason)
    await expect(rejectedRow).toBeVisible()
    await expect(rejectedRow).toContainText(/已驳回|REJECTED/)
    await expect(rejectedRow).toContainText(`驳回原因：${rejectReason}`)

    resubmittedLeaveId = await internship.submitLeave({
      startDate,
      endDate,
      reason: resubmitReason
    })
    expect(resubmittedLeaveId).not.toBe('')
    expect(resubmittedLeaveId).not.toBe(rejectedLeaveId)
  })

  test('实习导师对整改重交单再次审批通过', async ({ page }) => {
    expect(resubmittedLeaveId).not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const internship = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await internship.approve({ leaveId: resubmittedLeaveId, reason: resubmitReason })
  })

  test('学生刷新后看到已通过并真实办理销假', async ({ page }) => {
    expect(resubmittedLeaveId).not.toBe('')
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const internship = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await internship.openLeave()
    await page.reload()
    await expect(page.getByRole('button', { name: '实习请假' })).toBeVisible()
    await internship.returnLeave({
      leaveId: resubmittedLeaveId,
      reason: resubmitReason,
      note: returnNote
    })
  })

  test('学校管理员核验驳回旧单与整改新单的最终状态和审计链', async ({ page }) => {
    expect(rejectedLeaveId).not.toBe('')
    expect(resubmittedLeaveId).not.toBe('')
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const internship = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)

    const rejected = await internship.openFinal(rejectedLeaveId)
    expect(rejected.status).toBe('REJECTED')
    expect(rejected.reviewComment).toBe(rejectReason)
    expect((rejected.auditTrail || []).map((item) => item.action)).toEqual(
      expect.arrayContaining(['APPLY', 'REVIEW_REJECT'])
    )

    const finalData = await internship.openFinal(resubmittedLeaveId)
    expect(finalData.status).toBe('RETURNED')
    expect(finalData.returnNote).toBe(returnNote)
    expect(finalData.previousReviewComment).toBe(rejectReason)
    expect((finalData.auditTrail || []).map((item) => item.action)).toEqual(
      expect.arrayContaining(['APPLY', 'REVIEW_APPROVE', 'RETURN_VERSIONED'])
    )
  })
})
