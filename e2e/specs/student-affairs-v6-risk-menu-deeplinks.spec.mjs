import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const DASHBOARD = '/admin/student-affairs/dashboard'
const CASES = [
  ['/admin/student-affairs/risk?priority=HIGH_CRITICAL', '高危 / 危急'],
  ['/admin/student-affairs/risk?overdueOnly=true', '已超时'],
  ['/admin/student-affairs/risk?unassignedOnly=true', '待分派'],
  ['/admin/student-affairs/risk?ownerId=me', '我负责的'],
  ['/admin/student-affairs/risk?status=FOLLOWING', '持续跟进']
]

async function dismissGuide(page) {
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function openDashboard(page) {
  await page.goto(`${config.staffBaseUrl}${DASHBOARD}`)
  await expect.poll(() => new URL(page.url()).pathname).toBe(DASHBOARD)
  await dismissGuide(page)
  await expect(page.locator('[data-workspace="sa-risk"]')).toBeVisible()
}

async function openRiskWorkspace(page) {
  const workspace = page.locator('[data-workspace="sa-risk"]')
  await workspace.click()
  await expect(workspace).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('[data-nav-path^="/admin/student-affairs/risk?"][data-deep-link="true"]')).toHaveCount(5)
}

test('V6 risk workspace deep links activate the matching real server queue', async ({ page }, testInfo) => {
  test.setTimeout(4 * 60 * 1000)
  await page.setViewportSize({ width: 1366, height: 768 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

  const results = []
  for (const [rawPath, queueLabel] of CASES) {
    await openDashboard(page)
    await openRiskWorkspace(page)
    const leaf = page.locator(`[data-nav-path="${rawPath}"]`)
    await expect(leaf).toBeVisible()
    await expect(leaf).toBeEnabled()
    await expect(leaf).toHaveAttribute('data-entry-type', 'TASK_QUEUE')
    await leaf.click()

    const expected = new URL(rawPath, config.staffBaseUrl)
    await expect.poll(() => new URL(page.url()).pathname).toBe(expected.pathname)
    for (const [key, value] of expected.searchParams.entries()) {
      await expect.poll(() => new URL(page.url()).searchParams.get(key)).toBe(value)
    }
    const activeQueue = page.locator('.sa-queue.is-on')
    await expect(activeQueue).toHaveCount(1)
    await expect(activeQueue).toContainText(queueLabel)
    await expect(page.locator('[data-workspace="sa-risk"]')).toHaveClass(/is-active/)
    await expect(page.locator(`[data-nav-path="${rawPath}"]`)).toHaveClass(/is-active/)
    results.push({ rawPath, queueLabel, resolvedUrl: page.url() })
  }

  const image = testInfo.outputPath('v6-risk-contextual-menu-1366.png')
  await page.screenshot({ path: image, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach('v6-risk-contextual-menu-1366', { path: image, contentType: 'image/png' })
  await testInfo.attach('v6-risk-contextual-menu-results', {
    body: JSON.stringify(results, null, 2),
    contentType: 'application/json'
  })
  expect(results).toHaveLength(5)
})
