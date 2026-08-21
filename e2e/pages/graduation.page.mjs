import { expect } from '../lib/observability.mjs'

const SYNTHETIC_MARKER = 'YUEKE E2E SYNTHETIC DOCUMENT'

function serializePdfObjects(objects) {
  let body = `%PDF-1.4\n%${SYNTHETIC_MARKER}\n`
  const offsets = [0]
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = Buffer.byteLength(body, 'ascii')
    body += `${id} 0 obj\n${objects[id]}\nendobj\n`
  }
  const xrefOffset = Buffer.byteLength(body, 'ascii')
  body += `xref\n0 ${objects.length}\n`
  body += '0000000000 65535 f \n'
  for (let id = 1; id < objects.length; id += 1) {
    body += `${String(offsets[id]).padStart(10, '0')} 00000 n \n`
  }
  body += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  return body
}

function buildSyntheticPdf({ label = SYNTHETIC_MARKER, pages = 1, targetBytes = 0 } = {}) {
  const pageCount = Math.max(1, Math.floor(Number(pages) || 1))
  const safeLabel = String(label).replace(/[()\\]/g, '')
  const objects = [null]
  const pageIds = []

  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>'
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'

  for (let pageNo = 1; pageNo <= pageCount; pageNo += 1) {
    const pageId = 4 + (pageNo - 1) * 2
    const contentId = pageId + 1
    pageIds.push(pageId)
    const pageText = `${SYNTHETIC_MARKER} ${safeLabel} PAGE ${pageNo}/${pageCount}`
    const stream = `BT /F1 14 Tf 54 720 Td (${pageText}) Tj ET\n`
    objects[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`
    objects[contentId] = `<< /Length ${Buffer.byteLength(stream, 'ascii')} >>\nstream\n${stream}endstream`
  }
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pageCount} >>`

  let body = serializePdfObjects(objects)
  const wantedBytes = Math.max(0, Math.floor(Number(targetBytes) || 0))
  if (wantedBytes > Buffer.byteLength(body, 'ascii')) {
    const paddingId = objects.length
    const paddingBytes = Math.max(1, wantedBytes - Buffer.byteLength(body, 'ascii'))
    const padding = 'X'.repeat(paddingBytes)
    objects[paddingId] = `<< /Length ${paddingBytes} >>\nstream\n${padding}\nendstream`
    body = serializePdfObjects(objects)
  }
  return Buffer.from(body, 'ascii')
}

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

export class StudentGraduationPage {
  constructor(page, baseUrl) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
  }

  async open() {
    await this.page.goto(`${this.baseUrl}/graduation`)
    await expect(this.page.getByRole('heading', { name: /按步骤完成我的毕业设计/ })).toBeVisible()
  }

  step(name) {
    const titles = {
      '任务书': '任务书确认',
      '开题': '开题论证'
    }
    const title = titles[name] || name
    const heading = this.page.getByRole('heading', { name: title, exact: true })
    return this.page.locator('.gd-step').filter({ has: heading }).first()
  }

  async signTaskbookIfNeeded() {
    const step = this.step('任务书')
    await expect(step).toBeVisible()
    if (await step.getByText(/已签署|已确认/).count()) return

    const openButton = step.getByRole('button').filter({ hasText: /查看|签署|确认任务书/ }).first()
    if (await openButton.count()) await openButton.click()
    const checkbox = step.locator('input[type=checkbox]')
    if (await checkbox.count() && !(await checkbox.isChecked())) await checkbox.check()
    const sign = step.getByRole('button', { name: /签署确认/ })
    if (await sign.count()) {
      const [response] = await Promise.all([
        this.page.waitForResponse((r) =>
          r.url().includes('/portal/graduation/taskbook/sign') && r.request().method() === 'POST'
        ),
        sign.click()
      ])
      await expectSuccessfulResponse(response, '学生签署任务书')
      await expect(step).toContainText(/已签署|已确认/)
    }
  }

  async submitProposal({ suffix, fileName, pages = 1, targetBytes = 0 }) {
    const step = this.step('开题')
    await expect(step).toBeVisible()
    const action = step.getByRole('button').filter({ hasText: /填写|修改|重交|提交开题|完善/ }).first()
    if (await action.count()) await action.click()

    const background = this.page.getByLabel('选题背景与研究依据', { exact: true })
    const plan = this.page.getByLabel('研究方案与进度计划', { exact: true })
    await expect(background).toBeVisible()
    await expect(plan).toBeVisible()
    await background.fill(`Playwright 背景 ${suffix}：验证真实浏览器交互和数据持久化。`)
    await plan.fill(`Playwright 计划 ${suffix}：学生提交、导师审核、管理员复核。`)
    const outcome = this.page.getByLabel('预期成果', { exact: true })
    if (await outcome.count()) await outcome.fill(`Playwright 成果 ${suffix}：保留完整证据链。`)

    const pdf = buildSyntheticPdf({ label: String(suffix), pages, targetBytes })
    if (targetBytes) expect(pdf.length, 'large PDF fixture must meet the requested byte floor').toBeGreaterThanOrEqual(targetBytes)
    await this.page.locator('input[type=file]').setInputFiles({
      name: fileName,
      mimeType: 'application/pdf',
      buffer: pdf
    })

    const [response] = await Promise.all([
      this.page.waitForResponse((r) =>
        r.url().includes('/portal/graduation/proposal') && r.request().method() === 'POST'
      ),
      this.page.getByRole('button', { name: /提交开题报告/ }).click()
    ])
    await expectSuccessfulResponse(response, '学生提交开题报告')
    await expect(this.step('开题')).toContainText(/待审核|待审阅|已提交/)
  }

  async expectRejected(reason) {
    const step = this.step('开题')
    await expect(step).toContainText(/驳回|退回|修改/)
    await expect(step).toContainText(reason)
  }

  async expectApproved() {
    await expect(this.step('开题')).toContainText(/已通过|通过/)
  }
}

export class StaffGraduationPage {
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

  async openProposals(tab = 'PENDING_REVIEW') {
    const query = new URLSearchParams({ batchId: this.fixture.batchId, tab })
    await this.page.goto(`${this.baseUrl}/admin/graduation/proposals?${query}`)

    await this.dismissGuideIfPresent()
    await expect(this.page.getByRole('heading', { name: '开题审核', exact: true })).toBeVisible()
    await expect(this.page.locator('.pr-split')).toBeVisible()
    await this.dismissGuideIfPresent()
  }

  async selectStudent(expectedPages = 1) {
    await this.dismissGuideIfPresent()

    const detail = this.page.locator('.prc')
    if (await detail.count() && await detail.isVisible()) {
      await expect(detail).toContainText(this.fixture.topicTitle)
      await this.expectDocumentViewer(expectedPages)
      return
    }

    const row = this.page.locator('.pr-row').first()
    await expect(row).toBeVisible()
    await this.dismissGuideIfPresent()
    await row.click()
    await expect(detail).toBeVisible()
    await expect(detail).toContainText(this.fixture.topicTitle)
    await this.expectDocumentViewer(expectedPages)
  }

  async expectDocumentViewer(expectedPages = 1) {
    await expect(this.page.locator('.gd-review-workspace')).toBeVisible()
    const adapter = this.page.locator('[data-preview-adapter="pdf"]')
    await expect(adapter).toBeVisible()
    await expect(adapter.locator('canvas')).toHaveCount(expectedPages)
    await expect(adapter.locator('canvas[data-zoom]').first()).toBeVisible()
    await expect(this.page.locator('.dv-toolbar')).toContainText(`1 / ${expectedPages}`)

    if (expectedPages >= 60) {
      const initiallyRendered = await adapter.locator('canvas[data-zoom]').count()
      expect(initiallyRendered, `${expectedPages}-page PDF must not eagerly render the whole document`).toBeLessThan(20)
      const lastPage = adapter.locator(`[data-page="${expectedPages}"]`)
      await lastPage.scrollIntoViewIfNeeded()
      await expect(lastPage.locator('canvas')).toHaveAttribute('data-zoom', /.+/)
    }
  }

  async waitForPendingQueueReload() {
    return this.page.waitForResponse((r) => {
      if (r.request().method() !== 'GET') return false
      const url = new URL(r.url())
      return url.pathname.endsWith('/graduation/proposals')
        && url.searchParams.get('status') === 'PENDING_REVIEW'
    })
  }

  async expectReviewedStudentLeftPendingQueue(response, reloadResponse, expectedStatus, action) {
    const reviewBody = await expectSuccessfulResponse(response, action)
    expect(reviewBody?.data?.status, `${action} must return the canonical reviewed status`).toBe(expectedStatus)

    const queueBody = await expectSuccessfulResponse(reloadResponse, `${action}后重载待审队列`)
    const pendingItems = queueBody?.data?.items || []
    expect(
      pendingItems.some((item) => item.topicTitle === this.fixture.topicTitle),
      `${action}后原学生不得继续留在 PENDING_REVIEW 服务端队列`
    ).toBeFalsy()
    await expect(
      this.page.locator('.pr-row').filter({ hasText: this.fixture.topicTitle })
    ).toHaveCount(0)
  }

  async reject(reason) {
    const textarea = this.page.getByPlaceholder('批注将随批阅结果同步学生端…')
    await expect(textarea).toBeEnabled()
    await textarea.fill(reason)
    const pendingReload = this.waitForPendingQueueReload()
    const [response, reloadResponse] = await Promise.all([
      this.page.waitForResponse((r) =>
        r.url().includes('/graduation/proposals/')
        && new URL(r.url()).pathname.endsWith('/review')
        && r.request().method() === 'POST'
      ),
      pendingReload,
      this.page.getByRole('button', { name: /驳回当前版本/ }).click()
    ])
    await this.expectReviewedStudentLeftPendingQueue(response, reloadResponse, 'REJECTED', '导师驳回开题报告')
  }

  async approve() {
    await expect(this.page.getByRole('button', { name: /通过当前版本/ })).toBeEnabled()
    const pendingReload = this.waitForPendingQueueReload()
    const [response, reloadResponse] = await Promise.all([
      this.page.waitForResponse((r) =>
        r.url().includes('/graduation/proposals/')
        && new URL(r.url()).pathname.endsWith('/review')
        && r.request().method() === 'POST'
      ),
      pendingReload,
      this.page.getByRole('button', { name: /通过当前版本/ }).click()
    ])
    await this.expectReviewedStudentLeftPendingQueue(response, reloadResponse, 'APPROVED', '导师通过开题报告')
  }

  async verifyAdminAudit() {
    await expect(this.page.locator('.prc')).toContainText(/已通过/)
    await expect(this.page.getByText('审批留痕')).toBeVisible()
    await expect(this.page.locator('.prc')).toContainText(/通过|批阅/)
  }
}
