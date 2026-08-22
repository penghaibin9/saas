import { expect } from '../lib/observability.mjs'

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function expectSuccessfulResponse(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} returned HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  if (body && Object.prototype.hasOwnProperty.call(body, 'code')) {
    expect(body.code, `${action} returned business error: ${text.slice(0, 800)}`).toBe(0)
  }
  return body
}

export class StudentInternshipApplicationPage {
  constructor(page, baseUrl, fixture) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fixture = fixture
  }

  async open() {
    await this.page.goto(`${this.baseUrl}/internship`)
    await expect(this.page.getByRole('button', { name: '正式申请' })).toBeVisible()
    await this.page.getByRole('button', { name: '正式申请' }).click()
    await expect(this.page.getByText('提交正式申请', { exact: true })).toBeVisible()
    await expect(this.page.getByText('我的申请', { exact: true })).toBeVisible()
  }

  form() {
    return this.page.locator('section.sp-card').filter({ hasText: '提交正式申请' }).first()
  }

  async submitSelfArranged({ companyName, positionName, workAddress, contactName, contactPhone, note, fileName }) {
    const form = this.form()
    await expect(form).toBeVisible()
    await form.locator('select').selectOption('SELF_ARRANGED')

    const textInputs = form.locator('input:not([type="file"])')
    await expect(textInputs).toHaveCount(5)
    await textInputs.nth(0).fill(companyName)
    await textInputs.nth(1).fill(positionName)
    await textInputs.nth(2).fill(workAddress)
    await textInputs.nth(3).fill(contactName)
    await textInputs.nth(4).fill(contactPhone)

    const uploadResponse = this.page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/files' && response.request().method() === 'POST'
    )
    await form.locator('input[type="file"]').setInputFiles({
      name: fileName,
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<<>>\n%%EOF\n')
    })
    const uploadBody = await expectSuccessfulResponse(await uploadResponse, '学生上传自主实习证明材料')
    const fileId = String(uploadBody?.data?.fileId || uploadBody?.data?.id || '')
    expect(fileId, '真实文件上传必须返回 fileId').not.toBe('')
    await expect(form.getByText('材料已上传')).toBeVisible()

    await form.locator('textarea').fill(note)
    const saveResponse = this.page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/applications'
      && response.request().method() === 'PUT'
    )
    const submitResponse = this.page.waitForResponse((response) =>
      /^\/api\/v1\/portal\/internship\/context\/applications\/[^/]+\/submit$/.test(apiPath(response))
      && response.request().method() === 'POST'
    )
    await form.getByRole('button', { name: '保存并提交' }).click()
    const saved = await expectSuccessfulResponse(await saveResponse, '学生保存自主实习申请')
    const submitted = await expectSuccessfulResponse(await submitResponse, '学生提交自主实习申请')
    const appId = String(saved?.data?.id || submitted?.data?.id || '')
    expect(appId, '自主实习申请必须返回 application id').not.toBe('')
    expect(submitted?.data?.status).toBe('PENDING_REVIEW')
    expect(String(submitted?.data?.evidenceFileId || saved?.data?.evidenceFileId || '')).toBe(fileId)
    await expect(this.page.getByText(note, { exact: false }).first()).toBeVisible()
    await expect(this.page.getByText(/待审核|PENDING_REVIEW/).first()).toBeVisible()
    return { appId, fileId, version: submitted?.data?.version, recordVersion: submitted?.data?.recordVersion }
  }

  async expectRejectedFeedback(note, rejectReason) {
    await this.open()
    await this.page.reload()
    await expect(this.page.getByRole('button', { name: '正式申请' })).toBeVisible()
    await this.page.getByRole('button', { name: '正式申请' }).click()
    await expect(this.page.getByText(note, { exact: false }).first()).toBeVisible()
    await expect(this.page.getByText(`驳回原因：${rejectReason}`, { exact: false }).first()).toBeVisible()
    await expect(this.page.getByText(/已驳回|REJECTED/).first()).toBeVisible()
  }

  async expectApprovedAndLanded({ companyName, positionName }) {
    await this.page.goto(`${this.baseUrl}/internship`)
    await expect(this.page.getByRole('button', { name: '我的实习' })).toBeVisible()
    await expect(this.page.getByText(companyName, { exact: false }).first()).toBeVisible()
    await expect(this.page.getByText(positionName, { exact: false }).first()).toBeVisible()
  }
}

export class StaffInternshipApplicationPage {
  constructor(page, baseUrl, fixture) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fixture = fixture
  }

  async dismissGuideIfPresent() {
    const skip = this.page.getByRole('button', { name: /跳过引导|跳过/ }).first()
    try { await skip.waitFor({ state: 'visible', timeout: 1500 }) } catch { return }
    await skip.click()
    await this.page.locator('.tour-mask').waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
  }

  url({ status = 'PENDING_REVIEW', appId = '' } = {}) {
    const query = new URLSearchParams({ batchId: this.fixture.batchId, type: 'SELF_ARRANGED', status })
    if (appId) query.set('id', appId)
    return `${this.baseUrl}/admin/internship/applications?${query}`
  }

  async openPending() {
    await this.page.goto(this.url())
    await expect(this.page.getByText('实习申请审核').first()).toBeVisible()
    await this.dismissGuideIfPresent()
  }

  async openApplication(appId) {
    await this.openPending()
    const row = this.page.locator('tbody tr').filter({ hasText: this.fixture.studentName }).first()
    await expect(row).toBeVisible()
    const detailResponse = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/applications/${appId}`
      && response.request().method() === 'GET'
    )
    await row.getByRole('button', { name: /审核|查看/ }).click()
    const body = await expectSuccessfulResponse(await detailResponse, '教师打开自主实习申请详情')
    expect(String(body?.data?.id || '')).toBe(String(appId))
    const drawer = this.page.locator('[class*="drawer"]').filter({ hasText: this.fixture.studentName }).last()
    await expect(this.page.getByText('自主实习证明材料', { exact: true })).toBeVisible()
    return body?.data || {}
  }

  async downloadEvidence(fileId) {
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/files/download/${fileId}`
      && response.request().method() === 'GET'
    )
    const downloadPromise = this.page.waitForEvent('download').catch(() => null)
    await this.page.getByRole('button', { name: '下载' }).last().click()
    const response = await responsePromise
    expect(response.ok(), `证明材料下载 HTTP ${response.status()}`).toBeTruthy()
    const download = await downloadPromise
    if (download) expect(await download.failure()).toBeNull()
  }

  async reject(appId, reason) {
    const detail = await this.openApplication(appId)
    const reject = this.page.getByRole('button', { name: '驳回' }).last()
    await expect(reject).toBeEnabled()
    await reject.click()
    const dialog = this.page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await dialog.locator('textarea').fill(reason)
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/applications/${appId}/review`
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '确认驳回' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '实习指导教师驳回自主实习申请')
    expect(body?.data?.status).toBe('REJECTED')
    return { ...detail, reviewed: body?.data }
  }

  async approve(appId) {
    const detail = await this.openApplication(appId)
    const approve = this.page.getByRole('button', { name: '通过并落实去向' }).last()
    await expect(approve).toBeEnabled()
    await approve.click()
    const dialog = this.page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    const responsePromise = this.page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/applications/${appId}/review`
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '通过并落实' }).click()
    const body = await expectSuccessfulResponse(await responsePromise, '实习指导教师通过并落实自主实习申请')
    expect(body?.data?.status).toBe('APPROVED')
    return { ...detail, reviewed: body?.data }
  }

  async openFinal(appId) {
    await this.page.goto(this.url({ status: 'ALL', appId }))
    await expect(this.page.getByText('实习申请审核').first()).toBeVisible()
    await this.dismissGuideIfPresent()
    const response = await this.page.waitForResponse((r) =>
      apiPath(r) === `/api/v1/internship/applications/${appId}` && r.request().method() === 'GET'
    ).catch(() => null)
    if (response) return (await expectSuccessfulResponse(response, '管理员读取申请最终详情'))?.data || {}
    const row = this.page.locator('tbody tr').filter({ hasText: this.fixture.studentName }).first()
    await expect(row).toBeVisible()
    const detailResponse = this.page.waitForResponse((r) =>
      apiPath(r) === `/api/v1/internship/applications/${appId}` && r.request().method() === 'GET'
    )
    await row.getByRole('button', { name: /查看|审核/ }).click()
    return (await expectSuccessfulResponse(await detailResponse, '管理员读取申请最终详情'))?.data || {}
  }
}
