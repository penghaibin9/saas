import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const views = [
  ['毕设总览', '/admin/graduation', 'dashboard'],
  ['待评阅开题', '/admin/graduation/proposals?tab=PENDING_REVIEW', 'proposal'],
  ['开题报告批阅', '/admin/graduation/proposals', 'proposal'],
  ['待评阅成果', '/admin/graduation/finals?tab=PENDING_REVIEW', 'final'],
  ['成果提交与批阅', '/admin/graduation/finals', 'final']
]
const viewports = [
  [1760, 900, 1], [1440, 900, 1], [1366, 768, 1], [1280, 800, 1], [1366, 768, 1.25]
]

async function dismissGuide(page) {
  for (let i = 0; i < 3; i++) {
    const mask = page.locator('.app-step-guide__mask:visible, .tour-mask:visible').first()
    if (!await mask.isVisible()) return
    const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
    if (await skip.isVisible()) await skip.click()
    else await page.keyboard.press('Escape')
    await expect(mask).toBeHidden()
  }
}

async function sizes(locator) {
  return locator.evaluateAll(elements => elements.filter(element => element.getClientRects().length).map(element => {
    const style = getComputedStyle(element), rect = element.getBoundingClientRect()
    return { className: element.className, font: parseFloat(style.fontSize), height: rect.height }
  }))
}

test.describe('Graduation original workspaces inside the existing shared shell', () => {
  test.setTimeout(5 * 60_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  for (const [label, path, kind] of views) {
    test(`${label}: readable content, unchanged batch and visible version controls`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
      const target = new URL(path, config.staffBaseUrl)
      target.searchParams.set('batchId', String(fixture.batchId))
      await page.goto(target.toString())
      await dismissGuide(page)
      const shell = page.locator('.graduation-portal.bpl-workspace')
      await expect(shell.locator('.tw-frame')).toHaveCount(1)
      const content = shell.locator('.gd-business-view')
      await expect(content).toBeVisible()
      if (kind === 'dashboard') await expect(content.locator('.gdb-page')).toBeVisible()
      else await expect(content.locator('.gd-review-workspace__contract')).toBeVisible()
      const before = page.url(), measurements = []
      try {
        for (const [width, height, zoom] of viewports) {
          await page.setViewportSize({ width, height })
          // CSS zoom probe matches the existing audit; this is not native browser zoom.
          await page.evaluate(scale => { document.documentElement.style.zoom = String(scale) }, zoom)
          const texts = content.locator(kind === 'dashboard'
            ? '.gdb-focus__main > p, .gdb-focus--empty p, .gdb-kpi > span, .gdb-work-row strong'
            : '.gd-review-workspace__contract span, .gd-review-workspace__contract b, .gd-review-workspace__evidence > summary')
          const measured = await sizes(texts)
          expect(measured.length, 'real content must be present, not an empty or failed load').toBeGreaterThan(0)
          for (const item of measured) expect(item.font, item.className).toBeGreaterThanOrEqual(12)
          const controls = await sizes(content.locator(kind === 'dashboard'
            ? '.gdb-focus__action, .gdb-work-row > .mp-link'
            : '.gd-review-workspace__evidence > summary'))
          for (const item of controls) {
            expect(item.font, item.className).toBeGreaterThanOrEqual(13)
            expect(item.height, item.className).toBeGreaterThanOrEqual(34 * zoom - 1)
          }
          if (kind === 'proposal') await expect(content.locator('.pr-pane .gd-review-workspace__queue')).toBeHidden()
          if (kind !== 'dashboard') {
            await expect(content.getByTestId('review-command-contract')).toHaveAttribute('data-material-version', /.+/)
            await expect(content.locator('.gd-review-workspace__review')).toBeVisible()
          }
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
          expect(overflow, 'no page-level horizontal overflow').toBeLessThanOrEqual(8)
          expect(page.url(), 'resizing must not change business context').toBe(before)
          expect(new URL(page.url()).searchParams.get('batchId')).toBe(String(fixture.batchId))
          measurements.push({ width, height, cssZoom: zoom, measured, controls, overflow })
          await page.screenshot({ path: testInfo.outputPath(`${kind}-${width}-${height}-${zoom}.png`), animations: 'disabled', fullPage: false })
        }
      } finally {
        await page.evaluate(() => { document.documentElement.style.zoom = '' })
      }
      await testInfo.attach('content-readability', { body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, label, path, measurements }, null, 2)), contentType: 'application/json' })
    })
  }
})
