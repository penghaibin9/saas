import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORTS = [
  { width: 1760, height: 900, zoom: 1 },
  { width: 1440, height: 900, zoom: 1 },
  { width: 1366, height: 768, zoom: 1 },
  { width: 1280, height: 800, zoom: 1 },
  { width: 1366, height: 768, zoom: 1.25 } // CSS zoom, same probe as the existing 24-page audit.
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

async function expectPanel(page, panel, batchId) {
  await expect.poll(() => {
    const url = new URL(page.url())
    return [url.pathname, url.searchParams.get('panel'), url.searchParams.get('batchId')]
  }).toEqual(['/admin/graduation/students', panel, String(batchId)])
  await expect(page.locator('.graduation-portal .tw-main .gd-student-workspace')).toBeVisible()
  await expect(page.locator('.gd-student-page .loading-state')).toBeHidden()
  await expect(page.locator('.gd-student-page .error-state')).toHaveCount(0)
  await dismissGuide(page)
}

test.describe('Graduation original student workspace presentation', () => {
  test.setTimeout(8 * 60_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const url = new URL('/admin/graduation/students', config.staffBaseUrl)
    url.searchParams.set('batchId', String(fixture.batchId))
    url.searchParams.set('panel', 'roster')
    await page.goto(url.toString())
    await dismissGuide(page)
    await expectPanel(page, 'roster', fixture.batchId)
  })

  test('original task groups switch through their existing queries, with selected-state feedback', async ({ page }) => {
    const groups = page.locator('.gd-primary-tabs')
    await expect(groups.getByRole('button')).toHaveCount(5)
    for (const item of [
      { group: '进度与风险', initial: 'progress', task: '风险学生', target: 'risk' },
      { group: '选题 / 导师 / 资格', initial: 'topic', task: '过程分组', target: 'grouping' },
      { group: '材料 / 答辩', initial: 'materials', task: '答辩组', target: 'defense' }
    ]) {
      await groups.getByRole('button', { name: item.group, exact: true }).click()
      await expectPanel(page, item.initial, fixture.batchId)
      await expect(groups.getByRole('button', { name: item.group, exact: true })).toHaveAttribute('aria-pressed', 'true')
      await page.locator('.gd-local-views').getByRole('button', { name: item.task, exact: true }).click()
      await expectPanel(page, item.target, fixture.batchId)
      await expect(page.locator('.gd-local-views').getByRole('button', { name: item.task, exact: true })).toHaveAttribute('aria-pressed', 'true')
    }
    // The pre-existing parent grad-qual -> roster compatibility redirect is a separate audit finding.
    // This focused spec does not claim end-to-end coverage for all eleven local panels.
  })

  test('readable student tasks and filters remain inside the existing shell at five probes', async ({ page }, testInfo) => {
    const measurements = []
    try {
      for (const viewport of VIEWPORTS) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.evaluate(zoom => { document.documentElement.style.zoom = String(zoom) }, viewport.zoom)
        await expectPanel(page, 'roster', fixture.batchId)
        const result = await page.locator('.gd-student-page').evaluate(root => {
          const visible = element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden'
          const measure = selector => [...root.querySelectorAll(selector)].filter(visible).map(element => ({
            text: element.textContent.trim().slice(0, 40),
            font: parseFloat(getComputedStyle(element).fontSize), height: element.getBoundingClientRect().height
          }))
          return {
            tasks: measure('.gd-primary-tabs button, .gd-local-views button'),
            fields: measure('.af__control'),
            helpers: measure('.gd-student-hero__metrics span, .af__label, .gd-import-contract li'),
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
          }
        })
        expect(result.tasks.length).toBeGreaterThanOrEqual(5)
        expect(result.fields.length).toBeGreaterThan(0)
        for (const control of [...result.tasks, ...result.fields]) {
          expect(control.font).toBeGreaterThanOrEqual(13)
          expect(control.height).toBeGreaterThanOrEqual(34 * viewport.zoom - 1)
        }
        for (const helper of result.helpers) expect(helper.font).toBeGreaterThanOrEqual(12)
        expect(result.overflow).toBeLessThanOrEqual(8)
        measurements.push({ ...viewport, ...result })
        await page.screenshot({ path: testInfo.outputPath(`students-${viewport.width}-${viewport.zoom}.png`), animations: 'disabled' })
      }
    } finally { await page.evaluate(() => { document.documentElement.style.zoom = '' }) }
    await testInfo.attach('student-workspace-measurements', {
      body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, scaleMethod: 'CSS zoom', measurements }, null, 2)),
      contentType: 'application/json'
    })
  })
})
