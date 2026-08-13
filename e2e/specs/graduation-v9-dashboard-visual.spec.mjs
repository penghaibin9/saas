import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORT = { width: 1440, height: 900 }

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

test.describe.serial('V9.2 U1 Dashboard Before evidence', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('Screenshot A · teacher dashboard · real API + isolated MySQL', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)

    const query = new URLSearchParams({ batchId: fixture.batchId })
    const dashboardResponse = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return url.pathname.endsWith('/api/v1/graduation/dashboard')
        && url.searchParams.get('batchId') === fixture.batchId
    })

    await page.goto(`${config.staffBaseUrl}/admin/graduation?${query}`)
    const response = await dashboardResponse
    expect(response.ok()).toBeTruthy()
    const envelope = await response.json()
    expect(envelope?.code, JSON.stringify(envelope)).toBe(0)

    await expect(page).toHaveURL(/\/admin\/graduation\?batchId=/)
    await expect(page.locator('.gdb-command-bar')).toBeVisible()
    await expect(page.locator('.gdb-todos')).toBeVisible()
    await expect(page.getByText(fixture.batchName, { exact: false }).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/正在加载毕业设计中心|真实接口不可用|权限上下文加载失败/)

    await settleVisual(page)

    const screenshot = testInfo.outputPath('gd-U1-dashboard-A-1440x900.png')
    await page.screenshot({
      path: screenshot,
      fullPage: false,
      animations: 'disabled',
      caret: 'hide'
    })

    const meta = {
      phase: 'A',
      card: 'U1',
      head: process.env.GITHUB_SHA || 'local',
      tenant: config.mentor.tenant,
      role: 'GD_MENTOR',
      batchId: fixture.batchId,
      batchName: fixture.batchName,
      viewport: VIEWPORT,
      route: `/admin/graduation?batchId=${fixture.batchId}`,
      fixture: {
        gdStudentId: fixture.gdStudentId,
        studentNo: fixture.studentNo,
        mentorName: fixture.mentorName,
        topicTitle: fixture.topicTitle
      },
      dashboard: {
        batchName: envelope?.data?.batchName || '',
        todoCount: Array.isArray(envelope?.data?.todos) ? envelope.data.todos.length : 0,
        riskCount: Array.isArray(envelope?.data?.riskAlerts) ? envelope.data.riskAlerts.length : 0,
        statCount: Array.isArray(envelope?.data?.stats) ? envelope.data.stats.length : 0
      }
    }
    const metadata = testInfo.outputPath('gd-U1-dashboard-A-meta.json')
    await fs.writeFile(metadata, JSON.stringify(meta, null, 2), 'utf8')

    await testInfo.attach('gd-U1-dashboard-A-1440x900', { path: screenshot, contentType: 'image/png' })
    await testInfo.attach('gd-U1-dashboard-A-meta', { path: metadata, contentType: 'application/json' })
  })
})
