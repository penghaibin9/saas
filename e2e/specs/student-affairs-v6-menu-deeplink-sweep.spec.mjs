import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const DASHBOARD = '/admin/student-affairs/dashboard'
const WORKSPACES = [
  '今日工作',
  '唯一学生360',
  '风险与重点学生',
  '谈心家校与回访',
  '请假与返校',
  '困难与资助',
  '违纪处分与教育',
  '宿舍与公寓',
  '活动与成长',
  '数字迎新',
  '心理专项',
  '统计与档案'
]

async function dismissGuide(page) {
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function waitForDashboard(page) {
  await expect.poll(() => new URL(page.url()).pathname).toBe(DASHBOARD)
  await expect(page.locator('[data-workspace]')).toHaveCount(12)
  await dismissGuide(page)
}

async function openWorkspace(page, label) {
  const button = page.locator('[data-workspace]').filter({ hasText: label }).first()
  await expect(button, `${label} workspace must exist`).toBeVisible()
  await button.click()
  await expect(button).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('[data-nav-path]:visible').first(), `${label} must expose at least one permitted third-level entry`).toBeVisible()
}

async function clickExactPath(page, path) {
  const index = await page.locator('[data-nav-path]').evaluateAll((nodes, expected) => {
    return nodes.findIndex((node) => node.dataset.navPath === expected && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0)
  }, path)
  expect(index, `visible third-level entry ${path} must still exist after returning`).toBeGreaterThanOrEqual(0)
  const leaf = page.locator('[data-nav-path]').nth(index)
  await expect(leaf).toBeVisible()
  await expect(leaf).toBeEnabled()
  await leaf.click()
}

async function expectDeepLink(page, rawPath) {
  const expected = new URL(rawPath, config.staffBaseUrl)
  await expect.poll(() => new URL(page.url()).pathname, { timeout: 12_000 }).toBe(expected.pathname)
  for (const [key, value] of expected.searchParams.entries()) {
    await expect.poll(() => new URL(page.url()).searchParams.get(key), { timeout: 12_000 }).toBe(value)
  }
  await expect(page.locator('.base-portal-layout')).toBeVisible()
  await expect(page.locator('.bpl-main')).toBeVisible()
  await expect(page.locator('#app')).not.toBeEmpty()
  await expect(page.locator('body')).not.toContainText('Cannot find module')
  await expect(page.locator('body')).not.toContainText('页面不存在')
}

test('V6 student-affairs sidebar real-clicks every visible third-level deep link', async ({ page }, testInfo) => {
  test.setTimeout(15 * 60 * 1000)
  await page.setViewportSize({ width: 1366, height: 768 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}${DASHBOARD}`)
  await waitForDashboard(page)

  const clicked = []
  const failures = []
  const seenPaths = new Set()

  for (const workspace of WORKSPACES) {
    await test.step(workspace, async () => {
      await openWorkspace(page, workspace)
      const leaves = await page.locator('[data-nav-path]:visible').evaluateAll((nodes) => nodes.map((node) => ({
        path: node.dataset.navPath,
        leaf: node.dataset.leaf || '',
        label: (node.textContent || '').replace(/\s+/g, ' ').trim()
      })).filter((item) => item.path))

      for (const item of leaves) {
        const evidenceKey = `${workspace} :: ${item.label} :: ${item.path}`
        if (seenPaths.has(item.path)) continue
        seenPaths.add(item.path)
        const before = new URL(page.url()).pathname + new URL(page.url()).search
        try {
          await clickExactPath(page, item.path)
          await expectDeepLink(page, item.path)
          clicked.push({ workspace, ...item, resolvedUrl: page.url() })

          const after = new URL(page.url()).pathname + new URL(page.url()).search
          if (after !== before) {
            await page.goBack()
            await waitForDashboard(page)
          }
          await openWorkspace(page, workspace)
        } catch (error) {
          failures.push({ key: evidenceKey, message: String(error?.message || error), url: page.url() })
          await page.goto(`${config.staffBaseUrl}${DASHBOARD}`)
          await waitForDashboard(page)
          await openWorkspace(page, workspace)
        }
      }
    })
  }

  const viewportPath = testInfo.outputPath('v6-sidebar-all-visible-deeplinks-1366.png')
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach('v6-sidebar-all-visible-deeplinks-1366', { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach('v6-sidebar-deeplink-click-matrix', {
    body: JSON.stringify({ workspaces: WORKSPACES, uniquePaths: seenPaths.size, clicked, failures }, null, 2),
    contentType: 'application/json'
  })

  expect(clicked.length, 'The visible V6 sidebar must expose a meaningful set of third-level routes').toBeGreaterThanOrEqual(24)
  expect(failures, 'Every visible permitted third-level route must resolve and return').toEqual([])
})
