import { expect } from '../lib/observability.mjs'

async function expectSuccessfulResponse(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(
    response.ok(),
    `${action} returned HTTP ${response.status()}: ${text.slice(0, 800)}`
  ).toBeTruthy()
  if (body && Object.prototype.hasOwnProperty.call(body, 'code')) {
    expect(body.code, `${action} returned business error: ${text.slice(0, 800)}`).toBe(0)
  }
  return body
}

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

export class StudentInternshipPage {
  constructor(page, baseUrl, fixture) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fixture = fixture
  }

  async openLeave() {
    await this.page.goto(`${this.baseUrl}/internship`)
    await expect(this.page.getByRole('button', { name: '实习请假' })).toBeVisible()
    await expect(this.page.getByText(this.fixture.companyName).first()).toBeVisible()
    await expect(this.page.getByText(this.fixture.positionName).first()).toBeVisible()
    await this.page.getByRole('button', { name: '实习请假' }).click()
    await expect(this.page.getByText('发起请假', { exact: true })).toBeVisible()
    await expect(this.page.getByText('我的请假', { exact: true })).toBeVisible()
  }

  leaveForm() {
    return this.page.locator('section.sp-card').filter({ hasText: '发起请假' }).first()
  }

  leaveRow(reason) {
    return this.page.locator('.repitem').filter({ hasText: reason }).first()
  }

  async submitLeave({ startDate, endDate, reason }) {
    const form = this.leaveForm()
    await expect(form).toBeVisible()
    await form.locator('select').selectOption('PERSONAL')
    const dates = form.locator('input[type="date"]')
    await expect(dates).toHaveCount(2)
    await dates.nth(0).fill(startDate)
    await dates.nth(1).fill(endDate)
    await form.locator('textarea').fill(reason)

    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response).endsWith('/api/v1/portal/internship/context/leaves')
      && response.request().method() === 'POST'
    )
    await form.getByRole('button', { name: '提交请假' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '学生提交实习请假')
    const leaveId = String(body?.data?.id || '')
    expect(leaveId, '学生提交请假响应必须返回 leave id').not.toBe('')

    const row = this.leaveRow(reason)
    await expect(row).toBeVisible()
    await expect(row).toContainText(/待审批|PENDING/)
    return leaveId
  }

  async returnLeave({ leaveId, reason, note }) {
    await this.openLeave()
    const row = this.leaveRow(reason)
    await expect(row).toBeVisible()
    await expect(row).toContainText(/已通过|APPROVED/)
    const button = row.getByRole('button', { name: '办理销假' })
    await expect(button).toBeEnabled()

    this.page.once('dialog', async (dialog) => {
      expect(dialog.type()).toBe('prompt')
      expect(dialog.message()).toContain('销假说明')
      await dialog.accept(note)
    })
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/portal/internship/context/leaves/${leaveId}/return`)
      && response.request().method() === 'POST'
    )
    await button.click()
    const body = await expectSuccessfulResponse(await responsePromise, '学生办理实习销假')
    expect(body?.data?.status).toBe('RETURNED')

    await expect(row).toContainText(/已销假|RETURNED/)
    await expect(row.getByRole('button', { name: '办理销假' })).toHaveCount(0)
  }
}

export class StaffInternshipLeavePage {
  constructor(page, baseUrl, fixture) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fixture = fixture
  }

  async dismissGuideIfPresent() {
    const skip = this.page.getByRole('button', { name: /跳过引导/ })
    if (await skip.count() && await skip.isVisible()) await skip.click()
  }

  url({ panel = 'pending', leaveId = '' } = {}) {
    const query = new URLSearchParams({ batchId: this.fixture.batchId, panel })
    if (leaveId) query.set('id', leaveId)
    return `${this.baseUrl}/admin/internship/leaves?${query}`
  }

  async openPending() {
    await this.page.goto(this.url({ panel: 'pending' }))
    await expect(this.page.getByText('请假审批').first()).toBeVisible()
    await this.dismissGuideIfPresent()
  }

  async selectLeave(leaveId) {
    const row = this.page.locator('.lv-item').filter({ hasText: this.fixture.studentNo }).first()
    await expect(row).toBeVisible()
    const detailResponse = this.page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/leaves/${leaveId}`)
      && response.request().method() === 'GET'
    )
    await row.click()
    await expectSuccessfulResponse(await detailResponse, '教师打开请假详情')
    const detail = this.page.locator('.lv-main')
    await expect(detail).toContainText(this.fixture.studentName)
    await expect(detail).toContainText(/待处理|待审批|PENDING/)
  }

  async approve({ leaveId, reason }) {
    await this.openPending()
    await this.selectLeave(leaveId)
    const detail = this.page.locator('.lv-main')
    await expect(detail).toContainText(reason)

    const approveButton = this.page.locator('.lv-foot').getByRole('button', { name: '通过' })
    await expect(approveButton).toBeEnabled()
    await approveButton.click()

    const dialog = this.page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText(this.fixture.studentName)
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/leaves/${leaveId}/review`)
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '通过' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '实习指导教师审批通过')
    expect(body?.data?.status).toBe('APPROVED')
  }

  async openFinal(leaveId) {
    const detailResponse = this.page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/leaves/${leaveId}`)
      && response.request().method() === 'GET'
    )
    await this.page.goto(this.url({ panel: 'all', leaveId }))
    await expect(this.page.getByText('请假审批').first()).toBeVisible()
    await this.dismissGuideIfPresent()
    const body = await expectSuccessfulResponse(await detailResponse, '管理员读取请假最终详情')
    return body?.data || {}
  }

  async verifyFinalAudit({ leaveId, returnNote }) {
    const data = await this.openFinal(leaveId)
    expect(data.status).toBe('RETURNED')
    expect(data.returnNote).toBe(returnNote)

    const actions = (data.auditTrail || []).map((item) => item.action)
    expect(actions).toContain('APPLY')
    expect(actions).toContain('REVIEW_APPROVE')
    expect(actions).toContain('RETURN_VERSIONED')

    const detail = this.page.locator('.lv-main')
    await expect(detail).toContainText(this.fixture.studentName)
    await expect(detail).toContainText(/已销假|RETURNED/)
    await expect(detail).toContainText('审批留痕')
    await expect(detail).toContainText(/APPLY|申请/)
    await expect(detail).toContainText(/REVIEW_APPROVE|通过/)
    await expect(detail).toContainText(/RETURN_VERSIONED|销假/)
  }
}
