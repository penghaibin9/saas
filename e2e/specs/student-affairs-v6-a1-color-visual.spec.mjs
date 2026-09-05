import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const ROUTE = '/admin/student-affairs/dashboard'
const SEMANTIC_COUNTS = Object.freeze({
  pendingTodo: 14,
  pendingLeave: 7,
  overdueLeave: 2,
  pendingAid: 5,
  pendingFunding: 3,
  pendingDiscipline: 1,
  riskStudents: 9
})

async function installSemanticColorFixture(page) {
  // Test-only mixed counts: keep the real identity, permission and HTTP path, but guarantee
  // that danger/warning/primary/neutral semantic states are all exercised even on an empty tenant.
  await page.route(/\/api\/v1\/student-affairs\/dashboard(?:\?|$)/, async (route) => {
    const response = await route.fetch()
    const envelope = await response.json()
    expect(envelope.code).toBe(0)
    for (const card of envelope.data.summaryCards || []) {
      if (Object.prototype.hasOwnProperty.call(SEMANTIC_COUNTS, card.key)) {
        card.value = SEMANTIC_COUNTS[card.key]
      }
    }
    envelope.data.riskSummary = {
      ...(envelope.data.riskSummary || {}),
      highCount: 4,
      criticalCount: 1,
      topRiskLevel: 'CRITICAL'
    }
    await route.fulfill({ response, json: envelope })
  })
}

async function openDashboard(page, viewport) {
  await page.setViewportSize(viewport)
  await installSemanticColorFixture(page)
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
    }
  }
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    document.querySelector('.bpl-main')?.scrollTo(0, 0)
  })
}

async function visualGeometry(page) {
  return page.evaluate(() => {
    const box = (selector) => {
      const node = document.querySelector(selector)
      const rect = node.getBoundingClientRect()
      const style = getComputedStyle(node)
      return {
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        background: style.backgroundColor,
        backgroundImage: style.backgroundImage,
        paddingLeft: parseFloat(style.paddingLeft),
        paddingRight: parseFloat(style.paddingRight)
      }
    }
    const rows = [...document.querySelectorAll('.sa-v6-queue-row')].map((node) => {
      const rect = node.getBoundingClientRect()
      return { top: rect.top, bottom: rect.bottom, height: rect.height }
    })
    const iconColors = [...document.querySelectorAll('.sa-v6-queue-row__icon')].slice(0, 5).map((node) => {
      const style = getComputedStyle(node)
      return `${style.color}|${style.backgroundColor}`
    })
    return {
      topbar: box('.bpl-topbar'),
      rail: box('.bpl-rail'),
      aside: box('.bpl-aside--workspace'),
      main: box('.bpl-main'),
      hero: box('.sa-v6-hero__summary'),
      flow: box('.sa-v6-flow'),
      rows,
      iconColors,
      overflowX: document.documentElement.scrollWidth - innerWidth,
      visibleText: document.querySelector('.sa-v6-page-shell')?.innerText || ''
    }
  })
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1760, height: 1000 }]) {
  test(`colorful V6 A1 shell geometry at ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    await openDashboard(page, viewport)
    const result = await visualGeometry(page)

    expect(result.topbar.height).toBeGreaterThanOrEqual(52)
    expect(result.topbar.height).toBeLessThanOrEqual(56)
    expect(result.rail.width).toBeGreaterThanOrEqual(viewport.width <= 1450 ? 60 : 62)
    expect(result.rail.width).toBeLessThanOrEqual(66)
    expect(result.aside.width).toBeGreaterThanOrEqual(viewport.width <= 1450 ? 210 : 228)
    expect(result.aside.width).toBeLessThanOrEqual(viewport.width <= 1450 ? 218 : 236)
    expect(result.main.paddingLeft).toBeGreaterThanOrEqual(viewport.width <= 1450 ? 10 : 14)
    expect(result.main.paddingRight).toBeGreaterThanOrEqual(viewport.width <= 1450 ? 10 : 14)
    expect(result.hero.height).toBeGreaterThanOrEqual(78)
    expect(result.hero.height).toBeLessThanOrEqual(92)
    expect(result.hero.backgroundImage).not.toBe('none')
    expect(result.flow.height).toBeGreaterThanOrEqual(28)
    expect(result.flow.height).toBeLessThanOrEqual(36)
    expect(result.rows[0].top).toBeLessThanOrEqual(290)
    expect(result.rows[0].height).toBeGreaterThanOrEqual(62)
    expect(result.rows[0].height).toBeLessThanOrEqual(72)
    expect(result.rows.filter((row) => row.bottom <= viewport.height).length).toBeGreaterThanOrEqual(viewport.width <= 1450 ? 3 : 4)
    expect(new Set(result.iconColors).size).toBeGreaterThanOrEqual(3)
    expect(result.overflowX).toBeLessThanOrEqual(1)
    expect(result.visibleText).not.toMatch(/DATA GAP|permissionKey|allowedActions|API\s|route\s/i)

    const path = testInfo.outputPath(`color-v6-a1-${viewport.width}x${viewport.height}.png`)
    await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach(`color-v6-a1-${viewport.width}x${viewport.height}`, { path, contentType: 'image/png' })
    await testInfo.attach(`color-v6-a1-${viewport.width}x${viewport.height}-geometry`, {
      body: JSON.stringify(result, null, 2),
      contentType: 'application/json'
    })
  })
}
