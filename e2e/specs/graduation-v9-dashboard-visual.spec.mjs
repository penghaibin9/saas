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

async function expectRoute(page, { path, batchId, tab = null, panel = null, rsel = null }) {
  await expect.poll(() => {
    const url = new URL(page.url())
    return {
      path: url.pathname,
      batchId: url.searchParams.get('batchId'),
      tab: url.searchParams.get('tab'),
      panel: url.searchParams.get('panel'),
      rsel: url.searchParams.get('rsel')
    }
  }).toEqual({ path, batchId, tab, panel, rsel })
}

test.describe.serial('V9.2 U1 Dashboard Gold evidence', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('Screenshot B · teacher 5-second dashboard + exact todo routes', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)

    const dashboardUrl = `${config.staffBaseUrl}/admin/graduation?batchId=${encodeURIComponent(fixture.batchId)}`
    const dashboardResponse = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return url.pathname.endsWith('/api/v1/graduation/dashboard')
        && url.searchParams.get('batchId') === fixture.batchId
    })
    await page.goto(dashboardUrl)
    const response = await dashboardResponse
    expect(response.ok()).toBeTruthy()
    const envelope = await response.json()
    expect(envelope?.code, JSON.stringify(envelope)).toBe(0)

    await expect(page.locator('.gdb-page')).toBeVisible()
    await expect(page.locator('.gdb-overview')).toBeVisible()
    await expect(page.locator('.gdb-kpis .gdb-kpi')).toHaveCount(5)
    await expect(page.getByText('今日优先', { exact: true })).toBeVisible()
    await expect(page.locator('.gdb-todos')).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/正在加载毕业设计中心|真实接口不可用|权限上下文加载失败/)

    await settleVisual(page)
    const screenshot = testInfo.outputPath('gd-U1-dashboard-B-1440x900.png')
    await page.screenshot({ path: screenshot, fullPage: false, animations: 'disabled', caret: 'hide' })

    const batchId = fixture.batchId
    const cases = [
      ['开题材料待审阅', { path: '/admin/graduation/proposals', batchId, tab: 'PENDING_REVIEW' }],
      ['开题未提交催交', { path: '/admin/graduation/proposals', batchId, tab: 'NOT_SUBMITTED' }],
      ['成果待审阅', { path: '/admin/graduation/finals', batchId, tab: 'PENDING_REVIEW' }],
      ['答辩组待发布', { path: '/admin/graduation/defense', batchId }],
      ['未处理风险', { path: '/admin/graduation/risk-archive', batchId, panel: 'risk' }]
    ]

    for (const [label, target] of cases) {
      await page.locator('.gdb-todo').filter({ hasText: label }).click()
      await expectRoute(page, target)
      await page.goto(dashboardUrl)
      await expect(page.locator('.gdb-todos')).toBeVisible()
    }

    const firstRisk = envelope?.data?.riskAlerts?.[0]
    if (firstRisk?.id) {
      await page.locator('.gdb-risk-row').first().click()
      await expectRoute(page, {
        path: '/admin/graduation/risk-archive',
        batchId,
        panel: 'risk',
        rsel: String(firstRisk.id)
      })
    }

    const meta = {
      phase: 'B',
      card: 'U1',
      head: process.env.GITHUB_SHA || 'local',
      tenant: config.mentor.tenant,
      role: 'GD_MENTOR',
      batchId,
      batchName: fixture.batchName,
      viewport: VIEWPORT,
      route: `/admin/graduation?batchId=${batchId}`,
      dashboard: {
        batchName: envelope?.data?.batchName || '',
        todoCount: Array.isArray(envelope?.data?.todos) ? envelope.data.todos.length : 0,
        riskCount: Array.isArray(envelope?.data?.riskAlerts) ? envelope.data.riskAlerts.length : 0,
        statCount: Array.isArray(envelope?.data?.stats) ? envelope.data.stats.length : 0
      },
      routeContracts: cases.map(([label, target]) => ({ label, ...target }))
    }
    const metadata = testInfo.outputPath('gd-U1-dashboard-B-meta.json')
    await fs.writeFile(metadata, JSON.stringify(meta, null, 2), 'utf8')

    await testInfo.attach('gd-U1-dashboard-B-1440x900', { path: screenshot, contentType: 'image/png' })
    await testInfo.attach('gd-U1-dashboard-B-meta', { path: metadata, contentType: 'application/json' })
  })
})
