import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const DASHBOARD = '/admin/student-affairs/dashboard'
const expectedWorkspaces = [
  ['sa-workbench', '01'],
  ['sa-profile', '02'],
  ['sa-risk', '03'],
  ['sa-talks', '04'],
  ['sa-leave', '05'],
  ['sa-aid', '06'],
  ['sa-discipline', '07'],
  ['sa-dorm', '08'],
  ['sa-activities', '09'],
  ['sa-orientation', '10'],
  ['sa-mental', '11'],
  ['sa-archive-stats', '12']
]

async function openDashboard(page) {
  await page.setViewportSize({ width: 1366, height: 768 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}${DASHBOARD}`)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
    }
  }
}

async function ensureWorkspaceOpen(page, key) {
  const button = page.locator(`[data-workspace="${key}"]`)
  await expect(button).toBeVisible()
  if ((await button.getAttribute('aria-expanded')) !== 'true') await button.click()
  await expect(button).toHaveAttribute('aria-expanded', 'true')
  return button
}

async function expectDestination(page, navPath) {
  const expected = new URL(navPath, config.staffBaseUrl)
  await expect.poll(() => new URL(page.url()).pathname).toBe(expected.pathname)
  for (const [key, value] of expected.searchParams.entries()) {
    await expect.poll(() => new URL(page.url()).searchParams.get(key)).toBe(value)
  }
  expect(new URL(page.url()).pathname).not.toBe('/security/403')
  await expect(page.locator('.bpl-main')).not.toBeEmpty()
}

async function returnToDashboard(page) {
  for (let step = 0; step < 4 && new URL(page.url()).pathname !== DASHBOARD; step++) {
    await page.goBack()
  }
  await expect.poll(() => new URL(page.url()).pathname).toBe(DASHBOARD)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
}

test('V6 student-affairs sidebar renders three waves and twelve workspaces at 1366', async ({ page }, testInfo) => {
  await openDashboard(page)
  await expect(page.locator('.bpl-tree__workspace-head strong')).toHaveText('学工业务工作区')
  await expect(page.locator('.bpl-tree__section')).toHaveCount(3)
  await expect(page.locator('.bpl-tree__section').nth(0)).toContainText('第一波 · 高频主线')
  await expect(page.locator('.bpl-tree__section').nth(1)).toContainText('第二波 · 业务闭环')
  await expect(page.locator('.bpl-tree__section').nth(2)).toContainText('第三波 · 生命周期 / 专项')
  await expect(page.locator('[data-workspace]')).toHaveCount(12)

  for (const [key, ordinal] of expectedWorkspaces) {
    const workspace = page.locator(`[data-workspace="${key}"]`)
    await expect(workspace).toBeVisible()
    await expect(workspace.locator('.bpl-tree__num')).toHaveText(ordinal)
  }

  const geometry = await page.evaluate(() => {
    const aside = document.querySelector('.bpl-aside--workspace')
    const main = document.querySelector('.bpl-main')
    return {
      asideWidth: aside.getBoundingClientRect().width,
      asideOverflowX: aside.scrollWidth - aside.clientWidth,
      mainWidth: main.getBoundingClientRect().width,
      bodyOverflowX: document.documentElement.scrollWidth - innerWidth
    }
  })
  expect(geometry.asideWidth).toBeGreaterThanOrEqual(210)
  expect(geometry.asideOverflowX).toBeLessThanOrEqual(1)
  expect(geometry.mainWidth).toBeGreaterThan(700)
  expect(geometry.bodyOverflowX).toBeLessThanOrEqual(1)

  const file = testInfo.outputPath('v6-student-affairs-sidebar-12-workspaces-1366.png')
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach('v6-student-affairs-sidebar-12-workspaces-1366', { path: file, contentType: 'image/png' })
})

for (const [key, ordinal] of expectedWorkspaces) {
  test(`V6 workspace ${ordinal} exposes real-clickable third-level routes`, async ({ page }, testInfo) => {
    test.setTimeout(180_000)
    await openDashboard(page)
    const workspace = await ensureWorkspaceOpen(page, key)
    const section = workspace.locator('xpath=following-sibling::*[1][contains(@class,"bpl-tree__leaves")]')
    await expect(section).toBeVisible()
    const leaves = await section.locator('button[data-leaf]').evaluateAll((buttons) => buttons.map((button) => ({
      label: button.dataset.leaf,
      path: button.dataset.navPath
    })))
    expect(leaves.length, `${key} must expose at least one visible third-level route`).toBeGreaterThan(0)

    const expanded = testInfo.outputPath(`v6-workspace-${ordinal}-expanded.png`)
    await page.screenshot({ path: expanded, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach(`v6-workspace-${ordinal}-expanded`, { path: expanded, contentType: 'image/png' })

    const visited = []
    for (let index = 0; index < leaves.length; index++) {
      const leaf = leaves[index]
      expect(leaf.path).toMatch(/^\//)
      await ensureWorkspaceOpen(page, key)
      const button = page.locator(`[data-workspace="${key}"] + .bpl-tree__leaves button[data-leaf="${leaf.label}"]`)
      await expect(button, `${key}/${leaf.label} must be visible and enabled`).toBeVisible()
      await expect(button).not.toHaveAttribute('aria-disabled', 'true')
      await button.click()
      await expectDestination(page, leaf.path)
      visited.push({ ...leaf, actual: page.url() })

      const destination = testInfo.outputPath(`v6-workspace-${ordinal}-leaf-${String(index + 1).padStart(2, '0')}.png`)
      await page.screenshot({ path: destination, fullPage: false, animations: 'disabled', caret: 'hide' })
      await testInfo.attach(`v6-workspace-${ordinal}-${leaf.label}`, { path: destination, contentType: 'image/png' })
      await returnToDashboard(page)
    }

    await testInfo.attach(`v6-workspace-${ordinal}-visited-routes`, {
      body: JSON.stringify(visited, null, 2),
      contentType: 'application/json'
    })
  })
}

test('V6 search-only deep links stay out of the sidebar but remain reachable through real function search', async ({ page }, testInfo) => {
  await openDashboard(page)
  const cases = [
    ['报到流程配置', '/admin/orientation/flow-config'],
    ['新生信息核验', '/admin/orientation/verify'],
    ['缴费与绿色通道', '/admin/orientation/payment'],
    ['迎新归档', '/admin/orientation/archive'],
    ['资助批次', '/admin/student-affairs/funding/batches'],
    ['困难认定异议', '/admin/student-affairs/aid/objections']
  ]
  const visited = []
  for (const [label, path] of cases) {
    await expect(page.locator(`button[data-leaf="${label}"]`)).toHaveCount(0)
    const input = page.locator('.bpl-cmdk--fn input')
    await input.fill(label)
    const result = page.locator('.bpl-cmdk--fn .bpl-cmdk__opt').filter({
      has: page.locator('.bpl-cmdk__opt-lb', { hasText: new RegExp(`^${label}$`) })
    }).first()
    await expect(result).toBeVisible()
    await result.click()
    await expectDestination(page, path)
    visited.push({ label, path, actual: page.url() })
    await returnToDashboard(page)
  }
  await testInfo.attach('v6-search-deep-links', {
    body: JSON.stringify(visited, null, 2),
    contentType: 'application/json'
  })
})
