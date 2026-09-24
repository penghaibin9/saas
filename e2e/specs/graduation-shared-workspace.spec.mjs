import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'
import { GRADUATION_WORKSPACES } from '../../frontend/src/modules/graduation/config/graduationWorkspaces.js'

const leaves = GRADUATION_WORKSPACES.flatMap(workspace => workspace.children).filter(leaf => !leaf.hidden)
const VIEWPORTS = [
  { width: 1760, height: 900, zoom: 1 },
  { width: 1440, height: 900, zoom: 1 },
  { width: 1366, height: 768, zoom: 1 },
  { width: 1280, height: 800, zoom: 1 },
  // Matches the existing 24-page audit's CSS-scale probe, not native browser zoom.
  { width: 1366, height: 768, zoom: 1.25 }
]

function targetUrl(path, batchId) {
  const url = new URL(path, config.staffBaseUrl)
  url.searchParams.set('batchId', String(batchId))
  return url.toString()
}

function routeState(page) {
  const url = new URL(page.url())
  return { path: url.pathname, query: [...url.searchParams].sort(), hash: url.hash }
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

async function expectSharedShell(page, batchId) {
  const shell = page.locator('.graduation-portal.bpl-workspace')
  await expect(shell).toHaveCount(1)
  await expect(shell.locator('.tw-frame')).toHaveCount(1)
  const businessView = shell.locator('.tw-main .gd-business-view')
  await expect(businessView).toBeVisible()
  await expect(shell.locator('.gbs')).toHaveCount(1)
  await expect(shell.getByRole('combobox', { name: '选择毕设批次', exact: true })).toHaveValue(String(batchId))
  await expect(shell.locator(':scope > .bpl-body')).toHaveCount(0)
  await expect(shell.getByRole('navigation', { name: '二级菜单', exact: true })).toBeVisible()
  await expect(shell.getByRole('navigation', { name: '三级菜单', exact: true })).toBeVisible()
  // Different real Graduation pages use h1/h2 according to their existing
  // semantic shell. Require a visible semantic heading, not an invented h1.
  await expect(businessView.getByRole('heading').first()).toBeVisible()
  return shell
}

async function expectDestination(page, path, batchId) {
  const expected = new URL(targetUrl(path, batchId))
  await expect.poll(() => {
    const current = new URL(page.url())
    return {
      path: current.pathname,
      query: Object.fromEntries([...expected.searchParams.keys()].map(key => [key, current.searchParams.get(key)]))
    }
  }).toEqual({ path: expected.pathname, query: Object.fromEntries(expected.searchParams) })
}

test.describe('Graduation existing shared shell integration', () => {
  test.setTimeout(10 * 60_000)
  let fixture

  test.beforeAll(async () => {
    expect(GRADUATION_WORKSPACES).toHaveLength(8)
    expect(leaves).toHaveLength(24)
    fixture = await prepareGraduationFixture()
  })

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(targetUrl('/admin/graduation', fixture.batchId))
    await dismissGuide(page)
    await expectSharedShell(page, fixture.batchId)
  })

  test('8 workspaces / 24 leaves navigate through the real shared menus with one batch context', async ({ page }, testInfo) => {
    const visited = []
    for (const workspace of GRADUATION_WORKSPACES) {
      for (const leaf of workspace.children.filter(item => !item.hidden)) {
        await test.step(`${workspace.label} / ${leaf.label}`, async () => {
          // Re-select the workspace because equivalent shortcuts may share a route.
          await page.getByRole('navigation', { name: '二级菜单', exact: true })
            .getByRole('button', { name: workspace.label, exact: true }).click()
          await dismissGuide(page)
          await page.getByRole('navigation', { name: '三级菜单', exact: true })
            .getByRole('button', { name: leaf.label, exact: true }).click()
          await expectDestination(page, leaf.path, fixture.batchId)
          await expectSharedShell(page, fixture.batchId)
          await dismissGuide(page)
          visited.push({ workspace: workspace.key, leaf: leaf.label, ...routeState(page) })
        })
      }
    }
    expect(visited).toHaveLength(24)
    await testInfo.attach('shared-shell-menu-coverage', {
      body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, visited }, null, 2)),
      contentType: 'application/json'
    })
  })

  test('opened tabs retain the real batch and pending-review query after leaving and reopening', async ({ page }) => {
    const pendingPath = '/admin/graduation/proposals?tab=PENDING_REVIEW'
    await page.goto(targetUrl(pendingPath, fixture.batchId))
    await expectDestination(page, pendingPath, fixture.batchId)
    await expectSharedShell(page, fixture.batchId)
    await dismissGuide(page)
    const pending = routeState(page)

    await page.getByRole('navigation', { name: '二级菜单', exact: true })
      .getByRole('button', { name: '模板与设置', exact: true }).click()
    await expectDestination(page, '/admin/graduation/templates', fixture.batchId)
    await expectSharedShell(page, fixture.batchId)
    await dismissGuide(page)
    const tabs = page.getByRole('tablist', { name: '已打开页面', exact: true })
    await tabs.getByRole('tab', { name: '待评阅开题', exact: true }).click()
    await expect.poll(() => routeState(page)).toEqual(pending)
    await expectSharedShell(page, fixture.batchId)

    await tabs.getByRole('button', { name: '关闭待评阅开题', exact: true }).click()
    await expectDestination(page, '/admin/graduation/templates', fixture.batchId)
    await expect(tabs.getByRole('tab', { name: '待评阅开题', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '恢复最近关闭的页签', exact: true }).click()
    await expect.poll(() => routeState(page)).toEqual(pending)
    await expectSharedShell(page, fixture.batchId)
  })

  test('batch control remains readable inside the shared shell at the existing five viewport probes', async ({ page }, testInfo) => {
    const measurements = []
    try {
      for (const viewport of VIEWPORTS) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.evaluate(zoom => { document.documentElement.style.zoom = String(zoom) }, viewport.zoom)
        const shell = await expectSharedShell(page, fixture.batchId)
        const select = shell.getByRole('combobox', { name: '选择毕设批次', exact: true })
        const size = await select.evaluate(element => {
          const style = getComputedStyle(element)
          const box = element.getBoundingClientRect()
          return { fontSize: parseFloat(style.fontSize), minHeight: parseFloat(style.minHeight), renderedHeight: box.height }
        })
        expect(size.fontSize).toBeGreaterThanOrEqual(13)
        expect(size.minHeight).toBeGreaterThanOrEqual(34)
        expect(size.renderedHeight).toBeGreaterThanOrEqual(34 * viewport.zoom - 1)
        measurements.push({ ...viewport, ...size })
        await page.screenshot({ path: testInfo.outputPath(`shared-shell-${viewport.width}-${viewport.height}-${viewport.zoom}.png`), fullPage: false, animations: 'disabled' })
      }
    } finally {
      await page.evaluate(() => { document.documentElement.style.zoom = '' })
    }
    await testInfo.attach('shared-shell-readability', {
      body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, scaleMethod: 'CSS zoom, matching existing audit', measurements }, null, 2)),
      contentType: 'application/json'
    })
  })
})
