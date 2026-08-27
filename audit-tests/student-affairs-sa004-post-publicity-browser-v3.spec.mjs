import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const saAdmin = {
  tenant: 'sandbox-school',
  username: 'e2e_sa_admin',
  password: 'E2eTest@2026'
}

async function jsonBody(response) {
  try { return await response.json() } catch { return {} }
}

test.describe.serial('Student Affairs SA-004 post-publicity real-time continuation', () => {
  test.describe.configure({ retries: 0 })

  test('restore original PUBLICITY state -> real Staff PC confirm -> GRANTED', async ({ page }) => {
    test.setTimeout(180_000)

    const source = JSON.parse(await fs.readFile(path.resolve('student-affairs-scholarship-audit-evidence.json'), 'utf8'))
    const manifest = JSON.parse(await fs.readFile(path.resolve('student-affairs-sa004-time-gate-manifest.json'), 'utf8'))
    const applicationId = String(source.applicationId || '')
    expect(applicationId).toBeTruthy()
    expect(String(source.exactHead || '')).toBe(String(process.env.E2E_TARGET_SHA || ''))
    expect(String(manifest.productSha || '')).toBe(String(process.env.E2E_TARGET_SHA || ''))
    expect(String(manifest.applicationId || '')).toBe(applicationId)

    const api500 = []
    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      }
    })

    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(saAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding/publicity`)
    await expect(page.getByRole('heading', { name: '资助公示待办', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: 'E2E学生A' }).first()
    await expect(row, 'restored scholarship application must still be visible in PUBLICITY queue').toBeVisible({ timeout: 20_000 })
    await expect(row).toContainText('奖学金')
    await expect(row).not.toContainText('申诉待复核')

    const confirmResponse = page.waitForResponse((response) => {
      try {
        const u = new URL(response.url())
        return u.pathname.endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/publicity-confirm`) && response.request().method() === 'POST'
      } catch { return false }
    })

    await row.getByRole('button', { name: '确认公示期满 → 获资助', exact: true }).click()
    const response = await confirmResponse
    const body = await jsonBody(response)
    expect(response.ok(), `publicity confirm HTTP ${response.status()} ${JSON.stringify(body)}`).toBeTruthy()
    expect(body.code).toBe(0)
    await expect(page.getByText('已确认获资助', { exact: true })).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('tbody tr').filter({ hasText: 'E2E学生A' })).toHaveCount(0, { timeout: 15_000 })
    expect(api500, 'no API 5xx during post-publicity Staff PC confirmation').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-sa004-post-publicity-evidence.json'), JSON.stringify({
      exactHead: process.env.E2E_TARGET_SHA || '',
      sourceRunId: String(manifest.sourceRunId || ''),
      sourceRunnerSha: String(manifest.runnerSha || ''),
      applicationId,
      publicityAt: manifest.publicityAt,
      dueAt: manifest.dueAt,
      confirmHttpStatus: response.status(),
      result: 'REAL_PASS',
      surface: 'STAFF_PC_REAL_PUBLICITY_CONFIRM'
    }, null, 2), 'utf8')
  })
})
