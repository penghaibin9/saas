import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const TARGETS = [
  ['导师与分配', '/admin/graduation/mentors?panel=list'],
  ['分配冲突检测', '/admin/graduation/mentors/conflicts'],
  ['题目库', '/admin/graduation/topic-lib?panel=list'],
  ['选题轮次', '/admin/graduation/topic-rounds?panel=rounds'],
  ['题目调整申请', '/admin/graduation/topic-changes']
]
const PROBES = [
  [1760, 900, 1], [1440, 900, 1], [1366, 768, 1], [1280, 800, 1],
  // Same CSS zoom probe as the existing usability audit, not native browser zoom.
  [1366, 768, 1.25]
]

function urlFor(path, batchId) {
  const url = new URL(path, config.staffBaseUrl)
  url.searchParams.set('batchId', String(batchId))
  return url.toString()
}

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

test.describe('Graduation planning leaf presentation under the existing workspace', () => {
  test.setTimeout(10 * 60_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  test('five existing leaf routes retain batch and readable working surfaces without shell changes', async ({ page }, testInfo) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const evidence = []
    try {
      for (const [title, path] of TARGETS) {
        await page.goto(urlFor(path, fixture.batchId))
        await dismissGuide(page)
        const shell = page.locator('.graduation-portal.bpl-workspace')
        const root = shell.locator('.gd-business-view')
        await expect(shell.locator('.tw-frame')).toHaveCount(1)
        await expect(root).toBeVisible()
        await expect(root).toHaveAttribute('data-planning-workspace', 'true')
        await expect(shell.getByRole('combobox', { name: '选择毕设批次', exact: true })).toHaveValue(String(fixture.batchId))
        const expected = new URL(urlFor(path, fixture.batchId))
        await expect.poll(() => {
          const url = new URL(page.url())
          return { path: url.pathname, batchId: url.searchParams.get('batchId') }
        }).toEqual({ path: expected.pathname, batchId: String(fixture.batchId) })
        // Exercise the real loaded page, not an intercepted API response or screenshot update.
        const workingSurface = title === '分配冲突检测' ? root.locator('.mc-summary') : root.locator('.af')
        await expect(workingSurface).toBeVisible()
        for (const [width, height, zoom] of PROBES) {
          await page.setViewportSize({ width, height })
          await page.evaluate(value => { document.documentElement.style.zoom = String(value) }, zoom)
          const measurement = await root.evaluate(element => {
            const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden'
            const nodes = selector => [...element.querySelectorAll(selector)].filter(visible)
            const dims = node => ({ font: parseFloat(getComputedStyle(node).fontSize), height: node.getBoundingClientRect().height })
            const summary = element.querySelector('.mc-summary')
            return {
              primary: nodes('.mp-cell-main,.mp-link,.gm-tabs__item,.gd-primary-tabs button,.af__ops button').map(dims),
              helpers: nodes('.af__label,.mp-cell-sub,.mc-summary small,.mc-summary__facts span,.mc-card > p').map(dims),
              controls: nodes('.af__control,.af__ops button,.gm-tabs__item,.gd-primary-tabs button').map(dims),
              summaryColumns: summary ? getComputedStyle(summary).gridTemplateColumns.split(' ').length : null,
              overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)
            }
          })
          expect(measurement.overflow, `${title}: page overflow`).toBeLessThanOrEqual(2)
          for (const item of measurement.primary) expect(item.font, title).toBeGreaterThanOrEqual(13)
          for (const item of measurement.helpers) expect(item.font, title).toBeGreaterThanOrEqual(12)
          for (const item of measurement.controls) expect(item.height, title).toBeGreaterThanOrEqual(34 * zoom - 1)
          if (title === '分配冲突检测') expect([1, 2]).toContain(measurement.summaryColumns)
          evidence.push({ title, path: new URL(page.url()).pathname, width, height, cssZoom: zoom, ...measurement })
          await page.screenshot({ path: testInfo.outputPath(`${TARGETS.findIndex(item => item[0] === title)}-${width}-${zoom}.png`), fullPage: false, animations: 'disabled' })
        }
      }
      // Removing the marker must be reactive when the same parent routes to another page.
      await page.evaluate(() => { document.documentElement.style.zoom = '' })
      await page.getByRole('navigation', { name: '二级菜单', exact: true })
        .getByRole('button', { name: '批次与实施', exact: true }).click()
      await dismissGuide(page)
      await page.getByRole('navigation', { name: '三级菜单', exact: true })
        .getByRole('button', { name: '学生与进度', exact: true }).click()
      await expect.poll(() => new URL(page.url()).pathname).toBe('/admin/graduation/students')
      await expect(page.locator('.gd-business-view')).toBeVisible()
      await expect.poll(() => page.locator('.gd-business-view').getAttribute('data-planning-workspace')).toBe(null)
    } finally {
      await page.evaluate(() => { document.documentElement.style.zoom = '' })
      await testInfo.attach('graduation-planning-readability', {
        body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, scaleMethod: 'CSS zoom', evidence }, null, 2)),
        contentType: 'application/json'
      })
    }
  })
})
