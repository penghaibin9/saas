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

function isLeaveDetailResponse(response) {
  return /^\/api\/v1\/student-affairs\/leave\/[^/]+$/.test(apiPath(response))
    && response.request().method() === 'GET'
}

export class StudentAffairsPortalPage {
  constructor(page, baseUrl, fixture) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fixture = fixture
  }

  async openLeave() {
    await this.page.goto(`${this.baseUrl}/campus-service`)
    const tab = this.page.getByRole('button', { name: '请假销假' })
    await expect(tab).toBeVisible()
    await tab.click()
    await expect(this.page.getByText('请假申请', { exact: true })).toBeVisible()
    await expect(this.page.getByText('请假 / 销假 / 续假记录', { exact: true })).toBeVisible()
  }

  form() {
    return this.page.locator('section.sp-card').filter({ hasText: '请假申请' }).first()
  }

  async submitLeave({ startDate, endDate, reason }) {
    await this.openLeave()
    const form = this.form()
    await expect(form).toBeVisible()
    await form.locator('select').selectOption('PERSONAL')
    const dates = form.locator('input[type="date"]')
    await expect(dates).toHaveCount(2)
    await dates.nth(0).fill(startDate)
    await dates.nth(1).fill(endDate)
    await form.locator('textarea').fill(reason)

    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/affairs/leave'
      && response.request().method() === 'POST'
    )
    await form.getByRole('button', { name: '提交请假' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '学生提交学工请假')
    const leaveId = String(body?.data?.id || body?.data?.leaveId || '')
    expect(leaveId, '学生提交学工请假响应必须返回 leave id').not.toBe('')
    expect(body?.data?.affairsStatus).toBe('COUNSELOR_REVIEW')

    // 学生端状态标签使用后端中文 label，不把测试绑死到某一种文案；
    // 业务状态由写接口响应精确断言，同时要求刷新后的真实记录卡可见。
    const current = this.page.locator('article.record').first()
    await expect(current).toBeVisible()
    await expect(current).toContainText('事假')
    await expect(current).toContainText(startDate)
    return leaveId
  }

  async submitCancel({ leaveId }) {
    await this.openLeave()
    const button = this.page.getByRole('button', { name: '申请销假' }).first()
    await expect(button).toBeEnabled()
    const row = button.locator('xpath=ancestor::article[contains(@class,"record")]')
    await expect(row).toBeVisible()

    this.page.once('dialog', async (dialog) => {
      expect(dialog.type()).toBe('confirm')
      await dialog.accept()
    })
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/portal/affairs/leave/${leaveId}/cancel`
      && response.request().method() === 'POST'
    )
    await button.click()
    const body = await expectSuccessfulResponse(await responsePromise, '学生申请销假')
    expect(body?.data?.affairsStatus).toBe('WAIT_CANCEL_LEAVE')
    await expect(this.page.getByRole('button', { name: '申请销假' })).toHaveCount(0)
  }
}

export class StaffStudentAffairsLeavePage {
  constructor(page, baseUrl, fixture) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fixture = fixture
  }

  async dismissGuideIfPresent() {
    const skip = this.page.getByRole('button', { name: /跳过引导|跳过/ }).first()
    try {
      await skip.waitFor({ state: 'visible', timeout: 1500 })
    } catch {
      return
    }
    await skip.click()
    await this.page.locator('.tour-mask').waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
  }

  async openApproval() {
    await this.page.goto(`${this.baseUrl}/admin/student-affairs/leave`)
    await expect(this.page.getByText('请假审批').first()).toBeVisible()
    await this.dismissGuideIfPresent()
  }

  async openFollowup() {
    await this.page.goto(`${this.baseUrl}/admin/student-affairs/leave/followup?status=WAIT_CANCEL_LEAVE`)
    await expect(this.page.getByText('延期销假').first()).toBeVisible()
    await this.dismissGuideIfPresent()
  }

  async clickExactQueueLeave(leaveId, action) {
    await this.dismissGuideIfPresent()
    const rows = this.page.locator('.lv-item')
    await expect(rows.first()).toBeVisible()
    const count = await rows.count()
    for (let index = 0; index < count; index += 1) {
      const row = rows.nth(index)
      if (!(await row.isVisible())) continue
      const detailResponse = this.page.waitForResponse(isLeaveDetailResponse)
      await row.click()
      const body = await expectSuccessfulResponse(await detailResponse, action)
      if (String(body?.data?.id || '') === String(leaveId)) {
        return { row, data: body.data }
      }
    }
    throw new Error(`当前学工请假队列未找到目标记录 ${leaveId}`)
  }

  async approve(leaveId) {
    await this.openApproval()
    const { data } = await this.clickExactQueueLeave(leaveId, '辅导员打开请假详情')
    expect(data.affairsStatus).toBe('COUNSELOR_REVIEW')
    const detail = this.page.locator('.lv-main')
    await expect(detail).toContainText(this.fixture.studentName)

    const approveButton = this.page.locator('.lv-foot').getByRole('button', { name: '通过' })
    await expect(approveButton).toBeEnabled()
    await approveButton.click()
    const dialog = this.page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/approve`
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '通过' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '辅导员审批学工请假')
    expect(body?.data?.affairsStatus).toBe('APPROVED')
  }

  async confirmCancel(leaveId) {
    await this.openFollowup()
    const { data } = await this.clickExactQueueLeave(leaveId, '辅导员打开待销假详情')
    expect(data.affairsStatus).toBe('WAIT_CANCEL_LEAVE')

    const action = this.page.locator('.lv-foot').getByRole('button', { name: '销假确认' })
    await expect(action).toBeEnabled()
    await action.click()
    await expect(this.page.getByText('销假确认', { exact: true }).last()).toBeVisible()

    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/cancel-confirm`
      && response.request().method() === 'POST'
    )
    await this.page.getByRole('button', { name: '确认销假' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '辅导员确认销假')
    expect(body?.data?.affairsStatus).toBe('CLOSED')
  }

  async verifyFinalAsAdmin(leaveId) {
    const query = new URLSearchParams({ studentId: this.fixture.studentId, status: 'CLOSED' })
    await this.page.goto(`${this.baseUrl}/admin/student-affairs/leave/ledger?${query}`)
    await expect(this.page.getByText('请假台账').first()).toBeVisible()
    await this.dismissGuideIfPresent()

    const buttons = this.page.getByRole('button', { name: '查看' })
    await expect(buttons.first()).toBeVisible()
    const count = await buttons.count()
    let data = null
    for (let index = 0; index < count; index += 1) {
      const detailResponse = this.page.waitForResponse(isLeaveDetailResponse)
      await buttons.nth(index).click()
      const body = await expectSuccessfulResponse(await detailResponse, '管理员打开请假台账详情')
      if (String(body?.data?.id || '') === String(leaveId)) {
        data = body.data
        break
      }
      await this.page.keyboard.press('Escape')
    }
    expect(data, `请假台账未找到目标记录 ${leaveId}`).toBeTruthy()
    expect(data.affairsStatus).toBe('CLOSED')

    const actions = (data.auditTrail || []).map((item) => item.action)
    expect(actions).toContain('APPLY')
    expect(actions).toContain('APPROVED')
    expect(actions).toContain('CANCEL_SUBMIT')
    expect(actions).toContain('CLOSED')

    await expect(this.page.getByText(/已销假|CLOSED/).last()).toBeVisible()
    await expect(this.page.getByText('审批留痕', { exact: true }).last()).toBeVisible()
    await expect(this.page.getByText('APPLY', { exact: true })).toBeVisible()
    await expect(this.page.getByText('APPROVED', { exact: true })).toBeVisible()
    await expect(this.page.getByText('CANCEL_SUBMIT', { exact: true })).toBeVisible()
    await expect(this.page.getByText('CLOSED', { exact: true })).toBeVisible()
  }
}
