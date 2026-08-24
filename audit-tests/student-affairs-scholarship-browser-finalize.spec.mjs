import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StudentLoginPage, StaffLoginPage } from '../pages/login.page.mjs'

const staff = {
  saAdmin: { tenant: 'sandbox-school', username: 'e2e_sa_admin', password: 'E2eTest@2026' }
}

async function freshStudentLogin(page) {
  await page.context().clearCookies()
  const login = new StudentLoginPage(page, config.studentBaseUrl)
  await login.login(config.student)
  return login
}

async function freshStaffLogin(page, account) {
  await page.context().clearCookies()
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(account)
  return login
}

async function jsonBody(response) {
  try { return await response.json() } catch { return {} }
}

async function chooseFundingItem(page, studentName = 'E2E学生A') {
  const item = page.locator('li.fd-qitem').filter({ hasText: studentName }).first()
  await expect(item).toBeVisible({ timeout: 20_000 })
  await item.click()
  await expect(page.locator('.fd-detail')).toContainText(studentName)
  return item
}

async function confirmDialog(page, title, confirmText) {
  const dialog = page.getByRole('dialog').filter({ hasText: title }).last()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: confirmText, exact: true }).click()
}

test.describe.serial('Student Affairs strict browser audit · SA-004 scholarship finalization', () => {
  test.describe.configure({ retries: 0 })

  test('backdated real publicity -> browser confirmation -> GRANTED -> student projection', async ({ page }) => {
    test.setTimeout(180_000)
    const evidencePath = path.resolve('student-affairs-scholarship-audit-evidence.json')
    const evidence = JSON.parse(await fs.readFile(evidencePath, 'utf8'))
    const applicationId = String(evidence.applicationId || '')
    const revisedStatement = String(evidence.revisedStatement || '')
    expect(applicationId).toBeTruthy()

    const api500 = []
    const consoleErrors = []
    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push(text)
    })

    await test.step('SA admin confirms expired publicity through real workbench', async () => {
      await freshStaffLogin(page, staff.saAdmin)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding`)
      await expect(page.getByRole('heading', { name: '奖助管理工作台', exact: true })).toBeVisible()
      await chooseFundingItem(page)
      const detail = page.locator('.fd-detail')
      await expect(detail.getByText(revisedStatement, { exact: true })).toBeVisible({ timeout: 15_000 })
      await expect(detail).toContainText('公示中')
      const confirmPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/publicity-confirm`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '确认公示通过', exact: true }).click()
      await confirmDialog(page, '确认公示通过', '确认通过')
      const confirmed = await confirmPromise
      expect(confirmed.ok(), `publicity confirm HTTP ${confirmed.status()}`).toBeTruthy()
      const env = await jsonBody(confirmed)
      expect(env.code).toBe(0)
      expect(env.data?.status).toBe('GRANTED')
      await expect(detail).toContainText('已获资助', { timeout: 15_000 })
      await expect(detail.getByRole('button', { name: '确认公示通过', exact: true })).toHaveCount(0)
    })

    await test.step('student sees the granted scholarship in real PC portal', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=funding`)
      await expect(page.locator('.sp-panel__head').filter({ hasText: '奖学金与助学金' }).first()).toBeVisible()
      const record = page.locator('article.record').filter({ hasText: '奖学金' }).first()
      await expect(record).toBeVisible({ timeout: 15_000 })
      await expect(record).toContainText('已获资助')
      await expect(record.getByRole('button', { name: '提交申诉', exact: true })).toHaveCount(0)
      await expect(record.getByRole('button', { name: '修改后重提', exact: true })).toHaveCount(0)
    })

    expect(api500, 'no API 5xx during SA-004 finalization').toEqual([])
    expect(consoleErrors, 'no unexpected browser console errors during SA-004 finalization').toEqual([])

    evidence.finalStatus = 'GRANTED'
    evidence.studentGrantedVisible = true
    evidence.finalizedExactHead = process.env.E2E_TARGET_SHA || ''
    await fs.writeFile(evidencePath, JSON.stringify(evidence, null, 2), 'utf8')
  })
})
