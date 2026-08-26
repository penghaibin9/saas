import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const saAdmin = { tenant: 'sandbox-school', username: 'e2e_sa_admin', password: 'E2eTest@2026' }

async function freshStaffLogin(page) {
  await page.context().clearCookies()
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(saAdmin)
  return login
}

async function jsonBody(response) {
  try { return await response.json() } catch { return {} }
}

test.describe.serial('Student Affairs SA-005 real post-publicity continuation', () => {
  test.describe.configure({ retries: 0 })

  test('real SA admin confirms due GRANT through Staff PC publicity queue', async ({ page }) => {
    test.setTimeout(180_000)

    const evidence = JSON.parse(await fs.readFile(path.resolve('student-affairs-grant-audit-evidence.json'), 'utf8'))
    const manifest = JSON.parse(await fs.readFile(path.resolve('student-affairs-sa005-time-gate-manifest.json'), 'utf8'))
    expect(String(evidence.exactHead || '')).toBe(String(process.env.E2E_TARGET_SHA || ''))
    expect(String(manifest.productSha || '')).toBe(String(process.env.E2E_TARGET_SHA || ''))
    expect(String(evidence.applicationId || '')).toBe(String(manifest.applicationId || ''))
    expect(evidence.qualificationPrecondition).toBe('SA002_APPROVED_DIFFICULT_LIBRARY')

    const applicationId = String(evidence.applicationId)
    const api500 = []
    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      }
    })

    await freshStaffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding/publicity`)
    await expect(page.getByRole('heading', { name: '资助公示待办', exact: true })).toBeVisible({ timeout: 20_000 })

    const row = page.locator('tbody tr').filter({ hasText: 'E2E学生A' }).filter({ hasText: '助学金' }).first()
    await expect(row).toBeVisible({ timeout: 20_000 })
    await expect(row.getByRole('button', { name: '确认公示期满 → 获资助', exact: true })).toBeVisible()

    const responsePromise = page.waitForResponse((response) => {
      try {
        const u = new URL(response.url())
        return u.pathname.endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/publicity-confirm`) && response.request().method() === 'POST'
      } catch { return false }
    })
    await row.getByRole('button', { name: '确认公示期满 → 获资助', exact: true }).click()
    const response = await responsePromise
    const env = await jsonBody(response)
    expect(response.ok(), `grant post-publicity confirm HTTP ${response.status()} ${JSON.stringify(env)}`).toBeTruthy()
    expect(env.code).toBe(0)
    await expect(page.getByText('已确认获资助', { exact: false })).toBeVisible({ timeout: 15_000 })
    await expect(row).toHaveCount(0, { timeout: 15_000 })
    expect(api500, 'no API 5xx during SA-005 post-publicity confirmation').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-sa005-post-publicity-evidence.json'), JSON.stringify({
      result: 'REAL_PASS',
      surface: 'STAFF_PC',
      exactHead: process.env.E2E_TARGET_SHA || '',
      sourceRunId: String(manifest.sourceRunId || ''),
      applicationId,
      batchId: String(evidence.batchId || ''),
      appealId: String(evidence.appealId || ''),
      qualificationPrecondition: evidence.qualificationPrecondition,
      dueAt: String(manifest.dueAt || ''),
      preVersion: Number(manifest.preVersion || 0),
      confirmHttpStatus: response.status(),
      confirmedAt: new Date().toISOString()
    }, null, 2), 'utf8')
  })
})
