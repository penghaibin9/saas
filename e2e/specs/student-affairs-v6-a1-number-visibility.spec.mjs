import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

test('V6 A1 test-injected large counters are fully visible, not DOM-only', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  // Test-only data mutation; identity, permissions and API transport remain real.
  await page.route(/\/api\/v1\/student-affairs\/dashboard(?:\?|$)/, async (route) => {
    const response = await route.fetch()
    const envelope = await response.json()
    expect(envelope.code).toBe(0)
    for (const card of envelope.data.summaryCards) card.value = 123456
    envelope.data.riskSummary = { ...envelope.data.riskSummary, highCount: 123456, criticalCount: 123456, topRiskLevel: 'CRITICAL' }
    await route.fulfill({ response, json: envelope })
  })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dashboard`)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  await expect(page.locator('.sa-v6-queue-row')).toHaveCount(7)
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    if (await page.locator(selector).isVisible().catch(() => false)) {
      await page.getByRole('button', { name: /跳过引导|跳过/ }).first().click()
      await expect(page.locator(selector)).toBeHidden()
    }
  }
  await page.evaluate(async () => { await document.fonts.ready })
  const values = page.locator('[data-metric] dd, .sa-v6-risk-numbers dd, .sa-v6-queue-row__count strong')
  await expect(values).toHaveCount(14)
  const boxes = await values.evaluateAll((elements) => elements.map((element) => {
    const range = document.createRange()
    range.selectNodeContents(element)
    const text = range.getBoundingClientRect()
    const box = element.getBoundingClientRect()
    const lines = new Set([...range.getClientRects()].filter((rect) => rect.width > 0).map((rect) => Math.round(rect.top)))
    return {
      value: element.textContent.trim(),
      clipped: element.scrollWidth > element.clientWidth + 1,
      textOutsideBox: text.left < box.left - 1 || text.right > box.right + 1,
      wrapped: lines.size > 1
    }
  }))
  const viewportPath = testInfo.outputPath('v6-a1-large-counters-visible-1280.png')
  await page.screenshot({ path: viewportPath, animations: 'disabled', caret: 'hide' })
  await testInfo.attach('v6-a1-large-counters-visible', { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach('v6-a1-counter-boxes', { body: JSON.stringify(boxes, null, 2), contentType: 'application/json' })
  expect(boxes.every((item) => item.value === '123,456')).toBe(true)
  expect(boxes.filter((item) => item.clipped || item.textOutsideBox || item.wrapped), 'Each numeric value must be fully readable at the unchanged font size').toEqual([])
  const geometry = await page.evaluate(() => ({
    firstRowY: document.querySelector('.sa-v6-queue-row').getBoundingClientRect().top,
    overflow: document.documentElement.scrollWidth - innerWidth
  }))
  expect(geometry.firstRowY).toBeLessThanOrEqual(290)
  expect(geometry.overflow).toBeLessThanOrEqual(1)
})
