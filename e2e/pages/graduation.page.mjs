import { expect } from '../lib/observability.mjs'

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
    return this.page.locator('.gd-step').filter({ hasText: name }).first()
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
      await Promise.all([
        this.page.waitForResponse((r) => r.url().includes('/portal/graduation/taskbook/sign') && r.request().method() === 'POST'),
        sign.click()
      ])
      await expect(step).toContainText(/已签署|已确认/)
    }
  }

  async submitProposal({ suffix, fileName }) {
    const step = this.step('开题')
    await expect(step).toBeVisible()
    const action = step.getByRole('button').filter({ hasText: /填写|修改|重交|提交开题|完善/ }).first()
    if (await action.count()) await action.click()

    await step.getByLabel('选题背景与研究依据').fill(`Playwright 背景 ${suffix}：验证真实浏览器交互和数据持久化。`)
    await step.getByLabel('研究方案与进度计划').fill(`Playwright 计划 ${suffix}：学生提交、导师审核、管理员复核。`)
    const outcome = step.getByLabel('预期成果')
    if (await outcome.count()) await outcome.fill(`Playwright 成果 ${suffix}：保留完整证据链。`)

    await step.locator('input[type=file]').setInputFiles({
      name: fileName,
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n')
    })

    await Promise.all([
      this.page.waitForResponse((r) =>
        r.url().includes('/portal/graduation/proposal') && r.request().method() === 'POST'
      ),
      step.getByRole('button', { name: /提交开题报告/ }).click()
    ])
    await expect(step).toContainText(/待审核|待审阅|已提交/)
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
    const skip = this.page.getByRole('button', { name: /跳过引导/ })
    if (await skip.count() && await skip.isVisible()) await skip.click()
  }

  async openProposals(tab = 'PENDING_REVIEW') {
    const query = new URLSearchParams({ batchId: this.fixture.batchId, tab })
    await this.page.goto(`${this.baseUrl}/admin/graduation/proposals?${query}`)
    await expect(this.page.getByText('开题审核').first()).toBeVisible()
    await this.dismissGuideIfPresent()
  }

  async selectStudent() {
    // The proposal workbench automatically opens the first record in the current queue.
    // Keep that real page behavior instead of adding an unrelated second search that can
    // clear the queue before the core mentor-review action is exercised.
    const detail = this.page.locator('.prc')
    if (await detail.count() && await detail.isVisible()) {
      await expect(detail).toContainText(this.fixture.topicTitle)
      return
    }

    const row = this.page.locator('.pr-row').first()
    await expect(row).toBeVisible()
    await row.click()
    await expect(detail).toBeVisible()
    await expect(detail).toContainText(this.fixture.topicTitle)
  }

  async reject(reason) {
    const textarea = this.page.getByPlaceholder('批注将随批阅结果同步学生端…')
    await expect(textarea).toBeEnabled()
    await textarea.fill(reason)
    await Promise.all([
      this.page.waitForResponse((r) => r.url().includes('/graduation/proposals/') && new URL(r.url()).pathname.endsWith('/review') && r.request().method() === 'POST'),
      this.page.getByRole('button', { name: /驳回当前版本/ }).click()
    ])
    await expect(this.page.locator('.prc')).toContainText(/已驳回|驳回修改/)
  }

  async approve() {
    await expect(this.page.getByRole('button', { name: /通过当前版本/ })).toBeEnabled()
    await Promise.all([
      this.page.waitForResponse((r) => r.url().includes('/graduation/proposals/') && new URL(r.url()).pathname.endsWith('/review') && r.request().method() === 'POST'),
      this.page.getByRole('button', { name: /通过当前版本/ }).click()
    ])
    await expect(this.page.locator('.prc')).toContainText(/已通过/)
  }

  async verifyAdminAudit() {
    await expect(this.page.locator('.prc')).toContainText(/已通过/)
    await expect(this.page.getByText('审批留痕')).toBeVisible()
    await expect(this.page.locator('.prc')).toContainText(/通过|批阅/)
  }
}
