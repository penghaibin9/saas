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

async function assertRealWorkSurface(content, kind) {
  if (kind === 'dashboard') {
    await expect(content.locator('.gdb-page')).toBeVisible()
    return 'dashboard'
  }
  if (kind === 'proposal') {
    // Proposal is intentionally a native two-column workbench backed by
    // ProposalReviewCard; it does not use GraduationDocumentReviewWorkspace.
    await expect(content.locator('.pr-hero')).toBeVisible()
    await expect(content.locator('.pr-split')).toBeVisible()
    return 'proposal'
  }
  await expect(content.locator('.fr-command')).toBeVisible()
  const workspace = content.locator('.gd-review-workspace')
  if (await workspace.isVisible().catch(() => false)) return 'final-active'
  // An empty queue is a legitimate server state. Keep it visible rather than
  // fabricating a material/version solely for a visual probe.
  await expect(content).toContainText(/当前页签暂无成果|暂无|没有需要处理|当前队列/)
  return 'final-empty'
}

test.describe('Graduation original workspaces inside the existing shared shell', () => {
  test.setTimeout(5 * 60_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  for (const [label, path, kind] of views) {
    test(`${label}: readable content, unchanged batch and truthful version states`, async ({ page }, testInfo) => {
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
      const surface = await assertRealWorkSurface(content, kind)
      const before = page.url(), measurements = []
      try {
        for (const [width, height, zoom] of viewports) {
          await page.setViewportSize({ width, height })
          // CSS zoom probe matches the existing audit; this is not native browser zoom.
          await page.evaluate(scale => { document.documentElement.style.zoom = String(scale) }, zoom)
          const texts = content.locator(kind === 'dashboard'
            ? '.gdb-focus__main > p, .gdb-focus--empty p, .gdb-kpi > span, .gdb-work-row strong'
            : kind === 'proposal'
              ? '.pr-hero__copy > strong, .pr-hero__copy > p, .pr-hero__metrics small, .pr-list__head :is(span, small), .pr-row__name, .pr-row__sub'
              : '.fr-command__copy > strong, .fr-command__counts, .gd-review-workspace__contract span, .gd-review-workspace__contract b, .gd-review-workspace__evidence > summary')
          const measured = await sizes(texts)
          expect(measured.length, 'real page conclusion/work content must remain visible').toBeGreaterThan(0)
          for (const item of measured) expect(item.font, item.className).toBeGreaterThanOrEqual(12)
          const controls = await sizes(content.locator(kind === 'dashboard'
            ? '.gdb-focus__action, .gdb-work-row > .mp-link'
            : kind === 'proposal'
              ? '.mp-tab, .pr-pane__nav .mp-link, .pr-remind-action button'
              : '.mp-tab, .gd-review-workspace__nav button, .gd-review-workspace__evidence > summary'))
          for (const item of controls) {
            expect(item.font, item.className).toBeGreaterThanOrEqual(13)
            expect(item.height, item.className).toBeGreaterThanOrEqual(34 * zoom - 1)
          }
          if (kind === 'proposal') await expect(content.locator('.pr-pane .gd-review-workspace__queue')).toBeHidden()
          if (kind === 'final' && surface === 'final-active') {
            const contract = content.getByTestId('review-command-contract')
            await expect(contract).toBeVisible()
            // Do not manufacture a version. If the server has a canonical
            // reviewable target, its command contract must expose both values;
            // otherwise the existing blocked/empty state remains the truth.
            const materialVersion = await contract.getAttribute('data-material-version')
            const fileVersionId = await contract.getAttribute('data-file-version-id')
            if (materialVersion || fileVersionId) {
              expect(materialVersion, 'material version must accompany a canonical file target').toBeTruthy()
              expect(fileVersionId, 'file version must accompany a material version').toBeTruthy()
            }
            await expect(content.locator('.gd-review-workspace__review')).toBeVisible()
          }
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
          expect(overflow, 'no page-level horizontal overflow').toBeLessThanOrEqual(8)
          expect(page.url(), 'resizing must not change business context').toBe(before)
          expect(new URL(page.url()).searchParams.get('batchId')).toBe(String(fixture.batchId))
          measurements.push({ width, height, cssZoom: zoom, surface, measured, controls, overflow })
          await page.screenshot({ path: testInfo.outputPath(`${kind}-${width}-${height}-${zoom}.png`), animations: 'disabled', fullPage: false })
        }
      } finally {
        await page.evaluate(() => { document.documentElement.style.zoom = '' })
      }
      await testInfo.attach('content-readability', { body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, label, path, surface, measurements }, null, 2)), contentType: 'application/json' })
    })
  }
})