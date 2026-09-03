import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const DASHBOARD = '/admin/student-affairs/dashboard'

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

async function open(page, viewport = { width: 1366, height: 768 }, account = config.sandboxAdmin) {
  await page.setViewportSize(viewport)
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  await page.goto(`${config.staffBaseUrl}${DASHBOARD}`)
  await dismissGuide(page)
  await expect(page.locator('.sa-v6-workspace-nav')).toBeVisible()
  await expect(page.locator('.sa-v6-workspace')).toHaveCount(12)
}

async function expectPath(page, pathname, query = {}) {
  await expect.poll(() => new URL(page.url()).pathname).toBe(pathname)
  for (const [key, value] of Object.entries(query)) {
    await expect.poll(() => new URL(page.url()).searchParams.get(key)).toBe(value)
  }
  await expect(page.locator('.sa-v6-workspace-nav')).toBeVisible()
}

async function clickWorkspace(page, id, pathname) {
  const section = page.locator(`[data-workspace="${id}"]`)
  const head = section.locator('.sa-v6-workspace__head')
  await expect(head).toBeVisible()
  await head.click()
  await expectPath(page, pathname)
  await expect(section).toHaveClass(/is-route-active/)
  await expect(section).toHaveClass(/is-expanded/)
}

async function screenshot(page, testInfo, label) {
  const target = testInfo.outputPath(`${label}.png`)
  await page.screenshot({ path: target, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(label, { path: target, contentType: 'image/png' })
}

test('V6 workspace sidebar replaces the raw navPlan module tree at 1366', async ({ page }, testInfo) => {
  await open(page)
  await expect(page.locator('.bpl-tree')).toHaveCount(0)
  await expect(page.locator('.sa-v6-workspace-nav__header')).toContainText('学工工作区')
  await expect(page.locator('.sa-v6-workspace-nav__header')).toContainText('12×102')
  await expect(page.locator('[data-workspace="today"]')).toHaveClass(/is-route-active/)
  await expect(page.locator('[data-workspace="today"] .sa-v6-workspace__leaf')).toHaveCount(2)
  await page.locator('[data-workspace="today"] .sa-v6-workspace__group').filter({ hasText: '支撑动作' }).click()
  await expect(page.locator('[data-workspace="today"] .sa-v6-workspace__leaf')).toHaveCount(1)
  await expect(page.locator('[data-workspace="today"] .sa-v6-workspace__leaf')).toContainText('最近处理与审计')
  await expect.poll(() => new URL(page.url()).hash).toBe('#audit')
  await expect(page.locator('.sa-dashboard-panel--audit')).toBeVisible()

  const geometry = await page.evaluate(() => {
    const rail = document.querySelector('.bpl-rail').getBoundingClientRect()
    const aside = document.querySelector('.bpl-aside').getBoundingClientRect()
    const nav = document.querySelector('.sa-v6-workspace-nav')
    return {
      railWidth: rail.width,
      asideWidth: aside.width,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - innerWidth, nav.scrollWidth - nav.clientWidth)
    }
  })
  expect(geometry.railWidth).toBeLessThanOrEqual(65)
  expect(geometry.asideWidth).toBeGreaterThanOrEqual(205)
  expect(geometry.asideWidth).toBeLessThanOrEqual(215)
  expect(geometry.horizontalOverflow).toBeLessThanOrEqual(1)
  await screenshot(page, testInfo, 'v6-workspace-sidebar-1366')
})

test('all 12 workspaces navigate through real layouts and preserve the V6 sidebar', async ({ page }, testInfo) => {
  await open(page, { width: 1440, height: 900 })
  const entries = [
    ['student', '/admin/student/list'],
    ['risk', '/admin/student-affairs/risk'],
    ['talk', '/admin/student-affairs/talk'],
    ['leave', '/admin/student-affairs/leave'],
    ['aid', '/admin/student-affairs/aid'],
    ['discipline', '/admin/student-affairs/discipline'],
    ['dorm', '/admin/student-affairs/dormitory'],
    ['growth', '/admin/student-affairs/activity'],
    ['orientation', '/admin/orientation'],
    ['mental', '/admin/student-affairs/mental/summary'],
    ['stats', '/admin/student-affairs/stats'],
    ['today', DASHBOARD]
  ]
  const visited = []
  for (const [id, path] of entries) {
    await clickWorkspace(page, id, path)
    visited.push({ workspace: id, url: page.url() })
  }
  expect(visited).toHaveLength(12)
  await testInfo.attach('v6-workspace-entry-destinations', {
    body: JSON.stringify(visited, null, 2),
    contentType: 'application/json'
  })
})

test('student, class and orientation third-level groups stay linked across layouts', async ({ page }, testInfo) => {
  await open(page, { width: 1366, height: 768 })

  await clickWorkspace(page, 'student', '/admin/student/list')
  const student = page.locator('[data-workspace="student"]')
  await student.locator('.sa-v6-workspace__group').filter({ hasText: '班级与责任' }).click()
  await student.locator('.sa-v6-workspace__leaf').filter({ hasText: '班级列表' }).click()
  await expectPath(page, '/admin/campus-service/classes')
  await expect(page.locator('[data-workspace="student"]')).toHaveClass(/is-route-active/)

  await page.locator('[data-workspace="student"] .sa-v6-workspace__group').filter({ hasText: '数据治理' }).click()
  await page.locator('[data-workspace="student"] .sa-v6-workspace__leaf').filter({ hasText: '身份核验能力与记录' }).click()
  await expectPath(page, '/admin/student/identity')
  await expect(page.locator('[data-workspace="student"]')).toHaveClass(/is-route-active/)

  await clickWorkspace(page, 'orientation', '/admin/orientation')
  const orientation = page.locator('[data-workspace="orientation"]')
  await orientation.locator('.sa-v6-workspace__group').filter({ hasText: '阶段3 · 报到资格' }).click()
  await orientation.locator('.sa-v6-workspace__leaf').filter({ hasText: '报到资格' }).click()
  await expectPath(page, '/admin/orientation/qualification')
  await expect(page.locator('[data-workspace="orientation"]')).toHaveClass(/is-route-active/)
  await screenshot(page, testInfo, 'v6-workspace-orientation-qualification')
})

test('risk third-level quick queues preserve query intent and active leaf', async ({ page }) => {
  await open(page)
  await clickWorkspace(page, 'risk', '/admin/student-affairs/risk')
  const risk = page.locator('[data-workspace="risk"]')
  const overdue = risk.locator('.sa-v6-workspace__leaf').filter({ hasText: '超时待跟进' })
  await overdue.click()
  await expectPath(page, '/admin/student-affairs/risk', { overdueOnly: 'true', ownerId: 'me' })
  await expect(overdue).toHaveClass(/is-on/)
})

test('V6 workspace navigation supports keyboard entry and locked specialist leaves', async ({ page }, testInfo) => {
  await open(page, { width: 1366, height: 768 }, {
    tenant: config.sandboxAdmin.tenant,
    username: process.env.E2E_AFFAIRS_COUNSELOR_USERNAME || 'e2e_counselor_a',
    password: process.env.E2E_AFFAIRS_COUNSELOR_PASSWORD || 'E2eTest@2026'
  })
  const riskHead = page.locator('[data-workspace="risk"] .sa-v6-workspace__head')
  await riskHead.focus()
  await expect(riskHead).toBeFocused()
  await page.keyboard.press('Enter')
  await expectPath(page, '/admin/student-affairs/risk')

  await clickWorkspace(page, 'mental', '/admin/student-affairs/mental/summary')
  const mental = page.locator('[data-workspace="mental"]')
  await mental.locator('.sa-v6-workspace__group').filter({ hasText: '专项处置' }).click()
  const locked = mental.locator('.sa-v6-workspace__leaf.is-locked')
  await expect(locked).toHaveCount(2)
  await expect(locked.first()).toBeDisabled()
  await screenshot(page, testInfo, 'v6-workspace-counselor-locked-specialist')
})

test('V6 workspace sidebar remains readable in all six themes', async ({ page }, testInfo) => {
  await open(page, { width: 1366, height: 768 })
  for (const key of ['e', 'f', 'a', 'b', 'd', 'c']) {
    const control = page.locator(`button.bpl-thdot--${key}`)
    await control.click()
    await expect(control).toHaveAttribute('aria-pressed', 'true')
    const contrast = await page.locator('[data-workspace="today"] .sa-v6-workspace__name').evaluate((element) => {
      const canvas = document.createElement('canvas')
      canvas.width = 1
      canvas.height = 1
      const context = canvas.getContext('2d', { willReadFrequently: true })
      const luminance = (color) => {
        context.clearRect(0, 0, 1, 1)
        context.fillStyle = color
        context.fillRect(0, 0, 1, 1)
        const rgb = [...context.getImageData(0, 0, 1, 1).data].slice(0, 3).map((value) => {
          const channel = value / 255
          return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
        })
        return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
      }
      const foreground = luminance(getComputedStyle(element).color)
      const background = luminance(getComputedStyle(element.closest('.bpl-aside')).backgroundColor)
      return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05)
    })
    expect(contrast).toBeGreaterThanOrEqual(4.5)
    await screenshot(page, testInfo, `v6-workspace-theme-${key}`)
  }
})
