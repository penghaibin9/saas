import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { captureGoldCandidate, dynamicTextMasks, goldEnvironment } from '../lib/graduation-gold.mjs'
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

async function expectPrimaryActionRoute(page, { action, batchId }) {
  const [path, rawQuery = ''] = String(action.path || '').split('?')
  const expectedQuery = {
    ...Object.fromEntries(new URLSearchParams(rawQuery)),
    ...(action.query || {}),
    batchId: String(batchId)
  }
  const expectedKeys = Object.keys(expectedQuery)

  await expect.poll(() => {
    const url = new URL(page.url())
    return {
      path: url.pathname,
      query: Object.fromEntries(expectedKeys.map((key) => [key, url.searchParams.get(key)]))
    }
  }).toEqual({
    path,
    query: Object.fromEntries(Object.entries(expectedQuery).map(([key, value]) => [key, String(value)]))
  })
}

async function expectProjectedWorkItems(page, todayWorkItems) {
  await expect(page.locator('.gdb-work')).toBeVisible()
  await expect(page.locator('.gdb-focus')).toBeVisible()

  if (!todayWorkItems.length) {
    await expect(page.locator('.gdb-focus--empty')).toBeVisible()
    await expect(page.locator('.gdb-work-row')).toHaveCount(0)
    return
  }

  const first = todayWorkItems[0]
  const focus = page.locator('.gdb-focus')
  await expect(focus).toContainText(first.student?.name || first.business)
  await expect(focus).toContainText(first.business)
  await expect(focus).toContainText(first.waitingOn)
  await expect(focus).toContainText(first.nextActor)
  await expect(focus.locator('.gdb-focus__action')).toContainText(first.primaryAction.label)

  const remaining = todayWorkItems.slice(1)
  await expect(page.locator('.gdb-work-row')).toHaveCount(remaining.length)
  if (remaining.length) {
    const nextRow = page.locator('.gdb-work-row').first()
    await expect(nextRow).toContainText(remaining[0].student?.name || remaining[0].business)
    await expect(nextRow).toContainText(remaining[0].business)
  }
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

    const todayWorkItems = Array.isArray(envelope?.data?.todayWorkItems)
      ? envelope.data.todayWorkItems
      : []

    await expect(page.locator('.gdb-page')).toBeVisible()
    await expect(page.locator('.gdb-overview')).toBeVisible()
    await expect(page.locator('.gdb-kpis .gdb-kpi')).toHaveCount(5)
    await expect(page.locator('.gdb-todos')).toBeVisible()
    await expectProjectedWorkItems(page, todayWorkItems)
    await expect(page.locator('body')).not.toContainText(/正在加载毕业设计中心|真实接口不可用|权限上下文加载失败/)

    const firstPageSection = await page.locator('.gdb-page > section').first().getAttribute('class')
    expect(firstPageSection).toContain('gdb-overview')

    if (todayWorkItems.length) {
      await page.locator('.gdb-focus__action').click()
      await expectPrimaryActionRoute(page, { action: todayWorkItems[0].primaryAction, batchId: fixture.batchId })
      await page.goto(dashboardUrl)
      await expectProjectedWorkItems(page, todayWorkItems)
    }

    await settleVisual(page)
    const screenshot = testInfo.outputPath('gd-U1-dashboard-B-1440x900.png')
    await page.screenshot({ path: screenshot, fullPage: false, animations: 'disabled', caret: 'hide' })

    // U11 Gold candidate: preserve all business layout/status content while masking only
    // the security watermark and the run-scoped batch label that necessarily changes per CI run.
    const goldMasks = [
      page.locator('.gbs__select'),
      ...dynamicTextMasks(page, [fixture.runId, fixture.batchName]),
    ]
    const goldCandidateFailures = []
    for (const viewport of [VIEWPORT, { width: 1280, height: 800 }]) {
      try {
        await captureGoldCandidate(page, testInfo, {
          name: 'gd-U1-dashboard-GoldCandidate', ...viewport, masks: goldMasks,
        })
      } catch (error) {
        goldCandidateFailures.push(`${viewport.width}x${viewport.height}: ${error?.message || error}`)
      }
    }
    await page.setViewportSize(VIEWPORT)

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

    const riskRows = page.locator('.gdb-risk-row')
    if (await riskRows.count()) {
      const firstRiskRow = riskRows.first()
      const rowText = await firstRiskRow.innerText()
      const visibleRisk = (envelope?.data?.riskAlerts || []).find((risk) =>
        rowText.includes(String(risk.code || '')) && rowText.includes(String(risk.title || ''))
      )
      expect(visibleRisk?.id, `visible risk row must map to server risk: ${rowText}`).toBeTruthy()
      await firstRiskRow.click()
      await expectRoute(page, {
        path: '/admin/graduation/risk-archive',
        batchId,
        panel: 'risk',
        rsel: String(visibleRisk.id)
      })
    } else {
      await expect(page.locator('.gdb-risk-empty')).toBeVisible()
    }

    const environment = await goldEnvironment(page, testInfo)
    const meta = {
      phase: 'B',
      card: 'U1',
      head: environment.goldHead,
      goldHead: environment.goldHead,
      tenant: config.mentor.tenant,
      role: 'GD_MENTOR',
      batchId,
      batchName: fixture.batchName,
      fixtureVersion: { runId: fixture.runId, gdStudentId: fixture.gdStudentId },
      viewport: VIEWPORT,
      viewports: [VIEWPORT, { width: 1280, height: 800 }],
      route: `/admin/graduation?batchId=${batchId}`,
      browserProject: environment.browserProject,
      deviceScaleFactor: environment.deviceScaleFactor,
      language: environment.language,
      fontEnvironment: environment.fontEnvironment,
      dynamicZones: ['security-watermark', 'run-scoped-batch-label'],
      dashboard: {
        batchName: envelope?.data?.batchName || '',
        todoCount: Array.isArray(envelope?.data?.todos) ? envelope.data.todos.length : 0,
        workItemCount: todayWorkItems.length,
        workItemFields: todayWorkItems[0] ? Object.keys(todayWorkItems[0]).sort() : [],
        riskCount: Array.isArray(envelope?.data?.riskAlerts) ? envelope.data.riskAlerts.length : 0,
        statCount: Array.isArray(envelope?.data?.stats) ? envelope.data.stats.length : 0
      },
      routeContracts: cases.map(([label, target]) => ({ label, ...target }))
    }
    const metadata = testInfo.outputPath('gd-U1-dashboard-B-meta.json')
    await fs.writeFile(metadata, JSON.stringify(meta, null, 2), 'utf8')

    await testInfo.attach('gd-U1-dashboard-B-1440x900', { path: screenshot, contentType: 'image/png' })
    await testInfo.attach('gd-U1-dashboard-B-meta', { path: metadata, contentType: 'application/json' })
    expect(goldCandidateFailures, 'Dashboard Gold 的所有视口都必须匹配；失败时仍应完整采集每个 actual').toEqual([])
  })
})
