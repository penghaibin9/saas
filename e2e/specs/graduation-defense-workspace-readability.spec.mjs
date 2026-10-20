import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { graduationRoles } from '../lib/graduation-role-accounts.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const views = [
  ['defense', 'schedule', '答辩安排'],
  ['defense-scoring', 'scoring', '答辩评分'],
  ['defense-confirmation', 'confirmation', '答辩秘书确认'],
  ['grade-ledger', 'grades', '成绩台账']
]
const probes = [[1760, 900, 1], [1440, 900, 1], [1366, 768, 1], [1280, 800, 1], [1366, 768, 1.25]]
const marker = '.gd-business-view[data-graduation-defense-workspace]'

async function dismissGuide(page) {
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector).first()
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
    }
  }
}

async function inspect(page, zoom) {
  return page.locator(marker).evaluate((root, scale) => {
    const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden'
    const sized = selector => [...root.querySelectorAll(selector)].filter(visible).map(node => ({
      class: node.className,
      font: parseFloat(getComputedStyle(node).fontSize),
      height: node.getBoundingClientRect().height / scale
    }))
    return {
      overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      primary: sized('.ds-command > div:first-child > strong, .dg-command > div:first-child > strong, .mp-cell-main, .dt__td'),
      secondary: sized('.ds-command small, .dg-command small, .ds-command__facts span, .dg-command__facts span, .mp-cell-sub'),
      controls: sized('.ds-chip, .gp-mode__btn, .gp-tabs__item, .mp-tab, .gp-side .ie-in, .ds-receipt button, .dg-receipt button')
    }
  }, zoom)
}

test.describe.serial('graduation existing defense and grade workspaces', () => {
  let fixture
  // Readability probes are read-only and must reuse the canonical fixture.
  // Creating a second RUNNING batch for the same student would correctly trip
  // the student portal's multiple-current-batch safety gate and pollute later suites.
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  test('four original entries keep identity, batch and readable work surfaces', async ({ page }, testInfo) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    for (const [path, identity, title] of views) {
      const url = new URL(`${config.staffBaseUrl}/admin/graduation/${path}`)
      url.searchParams.set('batchId', fixture.batchId)
      await page.goto(url.toString())
      await expect(page.locator(marker)).toHaveAttribute('data-graduation-defense-workspace', identity)
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
      await dismissGuide(page)
      for (const [width, height, zoom] of probes) {
        await page.setViewportSize({ width, height })
        // CSS zoom probe only; this does not claim native browser zoom coverage.
        await page.evaluate(scale => { document.documentElement.style.zoom = String(scale) }, zoom)
        const result = await inspect(page, zoom)
        expect(result.primary.length).toBeGreaterThan(0)
        expect(result.secondary.length).toBeGreaterThan(0)
        expect(result.overflow, `${path} ${width} ${zoom}`).toBeLessThanOrEqual(2)
        for (const item of result.primary) expect(item.font, `${path} ${item.class}`).toBeGreaterThanOrEqual(13)
        for (const item of result.secondary) expect(item.font, `${path} ${item.class}`).toBeGreaterThanOrEqual(12)
        for (const item of result.controls) expect(item.height, `${path} ${item.class}`).toBeGreaterThanOrEqual(33.5)
        expect(new URL(page.url()).searchParams.get('batchId')).toBe(fixture.batchId)
        await testInfo.attach(`${identity}-${width}-${zoom}`, { body: JSON.stringify(result), contentType: 'application/json' })
      }
      await page.evaluate(() => { document.documentElement.style.zoom = '1' })
      await page.screenshot({ path: testInfo.outputPath(`${identity}.png`), fullPage: false, animations: 'disabled' })
    }
    await page.goto(`${config.staffBaseUrl}/admin/graduation/plagiarism-ledger?batchId=${fixture.batchId}`)
    await expect(page.locator('.gd-business-view')).toHaveAttribute('data-graduation-material-workspace', 'plagiarism')
    await expect(page.locator(marker)).toHaveCount(0)
  })

  for (const [account, path, responsibility] of [
    [graduationRoles.defenseExpert, 'defense-scoring', '本人评分'],
    [graduationRoles.defenseSecretary, 'defense-confirmation', '秘书确认']
  ]) {
    test(`${responsibility} keeps its real actor and entry identity`, async ({ page }) => {
      await new StaffLoginPage(page, config.staffBaseUrl).login(account)
      await page.goto(`${config.staffBaseUrl}/admin/graduation/${path}?batchId=${fixture.batchId}`)
      await expect(page.locator(marker)).toBeVisible()
      await expect(page.locator('.dg-command__facts > div:last-child')).toContainText(responsibility)
      // Read-only identity probe; canonical scoring/completeness remains covered
      // by the existing real-role golden journeys, not fabricated by this test.
    })
  }
})