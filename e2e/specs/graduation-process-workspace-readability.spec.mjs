import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const PANELS = [
  ['taskbook', '任务书'], ['guidance', '指导记录'], ['plan', '指导计划'],
  ['eval', '导师评价'], ['midterm', '中期检查']
]
const PROBES = [
  { width: 1760, height: 900, zoom: 1 }, { width: 1440, height: 900, zoom: 1 },
  { width: 1366, height: 768, zoom: 1 }, { width: 1280, height: 800, zoom: 1 },
  // Same CSS-scale probe as the existing audit; not native browser zoom.
  { width: 1366, height: 768, zoom: 1.25 }
]
const CONTEXT = { queue: 'process-readability', source: 'shared-workspace-polish' }

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

function workUrl(fixture, panel = 'taskbook') {
  const url = new URL('/admin/graduation/process', config.staffBaseUrl)
  for (const [key, value] of Object.entries({ ...CONTEXT, panel, batchId: fixture.batchId, studentId: fixture.gdStudentId })) url.searchParams.set(key, value)
  return url.toString()
}

async function expectContext(page, fixture, panel, path = '/admin/graduation/process') {
  await expect.poll(() => {
    const url = new URL(page.url())
    return { path: url.pathname, ...Object.fromEntries(['batchId', 'studentId', 'panel', 'queue', 'source'].map(key => [key, url.searchParams.get(key)])) }
  }).toEqual({ path, batchId: fixture.batchId, studentId: fixture.gdStudentId, panel, ...CONTEXT })
}

async function expectControls(locator, zoom = 1) {
  const dimensions = await locator.evaluateAll(elements => elements.filter(element => element.getClientRects().length).map(element => ({
    font: parseFloat(getComputedStyle(element).fontSize), height: element.getBoundingClientRect().height
  })))
  expect(dimensions.length).toBeGreaterThan(0)
  for (const value of dimensions) {
    expect(value.font).toBeGreaterThanOrEqual(13)
    expect(value.height).toBeGreaterThanOrEqual(34 * zoom - 1)
  }
  return dimensions
}

test.describe('Graduation original process workspace presentation', () => {
  test.setTimeout(10 * 60_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(workUrl(fixture))
    await expect(page.locator('.gd-business-view')).toHaveAttribute('data-graduation-process-workspace', 'workbench')
    await dismissGuide(page)
    // Use the real server search, not an assumed first-page position or API mock.
    await page.getByRole('searchbox', { name: '搜索毕设学生', exact: true }).fill(fixture.studentNo)
    await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
    await expectContext(page, fixture, 'taskbook')
  })

  test('five existing panels keep the same student and batch at all five viewport probes', async ({ page }, testInfo) => {
    const measurements = []
    try {
      for (const probe of PROBES) {
        await page.setViewportSize({ width: probe.width, height: probe.height })
        await page.evaluate(zoom => { document.documentElement.style.zoom = String(zoom) }, probe.zoom)
        for (const [panel, label] of PANELS) {
          await dismissGuide(page)
          const tabs = page.getByRole('navigation', { name: '过程指导页签', exact: true })
          await tabs.getByRole('button', { name: label, exact: true }).click()
          await expectContext(page, fixture, panel)
          await expect(tabs.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-pressed', 'true')
          await expect(page.locator('.gp-layout > .gp-side')).toHaveCount(1)
          await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
          await expect(page.getByRole('region', { name: label, exact: true })).toBeVisible()
          const dimensions = await expectControls(page.locator('.gp-tabs__item, .gp-side > .ie-in'), probe.zoom)
          const eyebrowSize = await page.locator('.gp-context__eyebrow').evaluate(element => parseFloat(getComputedStyle(element).fontSize))
          expect(eyebrowSize).toBeGreaterThanOrEqual(12)
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
          expect(overflow).toBeLessThanOrEqual(2)
          measurements.push({ panel, ...probe, dimensions, eyebrowSize, overflow })
        }
        await page.screenshot({ path: testInfo.outputPath(`process-${probe.width}-${probe.height}-${probe.zoom}.png`), animations: 'disabled', fullPage: false })
      }
    } finally { await page.evaluate(() => { document.documentElement.style.zoom = '' }) }
    await testInfo.attach('process-readability', { body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, scale: 'CSS zoom', measurements }, null, 2)), contentType: 'application/json' })
  })

  test('original guidance form stays readable and cancel returns to the original work context', async ({ page }) => {
    await page.getByRole('navigation', { name: '过程指导页签', exact: true }).getByRole('button', { name: '指导记录', exact: true }).click()
    await expectContext(page, fixture, 'guidance')
    await dismissGuide(page)
    await page.getByRole('button', { name: '＋ 新增指导记录', exact: true }).click()
    await expectContext(page, fixture, 'guidance', `/admin/graduation/process/${fixture.gdStudentId}/guidance`)
    await expect(page.locator('.gd-business-view')).toHaveAttribute('data-graduation-process-workspace', 'form')
    const content = page.locator('label').filter({ hasText: '指导内容' }).locator('textarea').first()
    await expect(content).toBeVisible()
    await expectControls(page.locator('.ie-form textarea.ie-in, .gd-form-footer .mp-btn'))
    expect(await content.evaluate(element => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(104)
    await page.getByRole('button', { name: '取消', exact: true }).click()
    await expectContext(page, fixture, 'guidance')
    await expect(page.locator('.gd-business-view')).toHaveAttribute('data-graduation-process-workspace', 'workbench')

    const studentUrl = new URL('/admin/graduation/students', config.staffBaseUrl)
    studentUrl.searchParams.set('batchId', fixture.batchId)
    await page.goto(studentUrl.toString())
    await expect(page.locator('.gd-student-page')).toBeVisible()
    await expect(page.locator('.gd-business-view')).not.toHaveAttribute('data-graduation-process-workspace', /.+/)
  })
})
