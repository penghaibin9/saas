import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const TARGETS = [
  { path: '/admin/graduation/material-center', marker: 'materials', surface: '.mc-page', controls: '.mc-tabs button, .mc-filters input, .mc-filters select, .mc-filters button' },
  { path: '/admin/graduation/plagiarism-ledger', marker: 'plagiarism', surface: '.gp-layout', controls: '.gp-side .ie-in, .gp-mode__btn' },
  { path: '/admin/graduation/review-tasks', marker: 'review', surface: '.w74-center', controls: '.w74-chip, .w74-toolbar__search input[type=search], .w74-refresh' }
]
const PROBES = [
  [1760, 900, 1], [1440, 900, 1], [1366, 768, 1], [1280, 800, 1],
  [1366, 768, 1.25] // CSS zoom, not native browser zoom.
]

async function dismissGuide(page) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const mask = page.locator('.app-step-guide__mask:visible, .tour-mask:visible').first()
    if (!await mask.isVisible()) return
    const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
    if (await skip.isVisible()) await skip.click()
    else await page.keyboard.press('Escape')
    await expect(mask).toBeHidden()
  }
}

function targetUrl(path, batchId) {
  const url = new URL(path, config.staffBaseUrl)
  url.searchParams.set('batchId', batchId)
  return url.toString()
}

async function measure(page, selector, zoom) {
  const controls = await page.locator(selector).evaluateAll(elements => elements.filter(e => e.getClientRects().length).map(e => ({
    font: parseFloat(getComputedStyle(e).fontSize), height: e.getBoundingClientRect().height
  })))
  expect(controls.length).toBeGreaterThan(0)
  for (const item of controls) {
    expect(item.font).toBeGreaterThanOrEqual(13)
    expect(item.height).toBeGreaterThanOrEqual(34 * zoom - 1)
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(2)
  return { controls, overflow }
}

test.describe('Graduation existing material, plagiarism and review surfaces', () => {
  test.setTimeout(8 * 60_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  })

  test('three real entries keep readable controls, batch identity and local scrolling', async ({ page }, testInfo) => {
    const results = []
    for (const target of TARGETS) {
      await page.goto(targetUrl(target.path, fixture.batchId))
      await expect(page.locator('.gd-business-view')).toHaveAttribute('data-graduation-material-workspace', target.marker)
      await expect(page.locator(target.surface)).toBeVisible()
      await dismissGuide(page)
      for (const [width, height, zoom] of PROBES) {
        await page.setViewportSize({ width, height })
        await page.evaluate(value => { document.documentElement.style.zoom = String(value) }, zoom)
        await expect.poll(() => new URL(page.url()).searchParams.get('batchId')).toBe(fixture.batchId)
        const dimensions = await measure(page, target.controls, zoom)
        results.push({ path: target.path, width, height, zoom, ...dimensions })
        await page.screenshot({ path: testInfo.outputPath(`${target.marker}-${width}-${height}-${zoom}.png`), fullPage: false, animations: 'disabled' })
      }
      await page.evaluate(() => { document.documentElement.style.zoom = '' })
    }
    await testInfo.attach('material-workspace-dimensions', { body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, scale: 'CSS zoom', results }, null, 2)), contentType: 'application/json' })
  })

  test('material view changes and refresh preserve the original batch without issuing review commands', async ({ page }) => {
    await page.goto(targetUrl(TARGETS[0].path, fixture.batchId))
    await expect(page.locator('.mc-tabs')).toBeVisible()
    await dismissGuide(page)
    const tabs = page.locator('.mc-tabs button')
    const count = await tabs.count()
    expect(count).toBeGreaterThan(1)
    for (let index = 0; index < count; index++) {
      await tabs.nth(index).click()
      await expect(tabs.nth(index)).toHaveAttribute('aria-pressed', 'true')
      await expect.poll(() => new URL(page.url()).searchParams.get('batchId')).toBe(fixture.batchId)
    }
    await page.reload()
    await expect(page.locator('.mc-tabs button[aria-pressed=true]')).toHaveCount(1)
    await expect(page.locator('.mc-summary article')).toHaveCount(6)
    // Leaving this family must remove the marker even though the parent is reused.
    await page.goto(targetUrl('/admin/graduation/students', fixture.batchId))
    await expect(page.locator('.gd-student-page')).toBeVisible()
    await expect(page.locator('.gd-business-view')).not.toHaveAttribute('data-graduation-material-workspace', /.+/)
  })
})
