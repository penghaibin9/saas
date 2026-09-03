import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const THEMES = ['e', 'f', 'a', 'b', 'd', 'c']
const DASHBOARD_API = /\/api\/v1\/student-affairs\/dashboard(?:\?|$)/

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

async function openShell(page, viewport) {
  await page.setViewportSize(viewport)
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dashboard`)
  await expect(page.locator('.base-portal-layout')).toBeVisible()
  await dismissGuide(page)
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
}

async function capture(page, testInfo, name) {
  const path = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path, contentType: 'image/png' })
}

async function assertTopbarGeometry(page) {
  const geometry = await page.evaluate(() => {
    const topbar = document.querySelector('.bpl-topbar')
    const search = document.querySelector('.bpl-cmdk--fn')
    const group = document.querySelector('.bpl-thdots')
    const buttons = [...document.querySelectorAll('.bpl-thdots button.bpl-thdot')]
    return {
      topbarOverflow: topbar.scrollWidth - topbar.clientWidth,
      searchRight: search.getBoundingClientRect().right,
      groupLeft: group.getBoundingClientRect().left,
      buttons: buttons.map((button) => {
        const rect = button.getBoundingClientRect()
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
        return {
          key: [...button.classList].find((name) => name.startsWith('bpl-thdot--')),
          width: rect.width,
          height: rect.height,
          centerHit: hit === button || button.contains(hit),
          label: button.getAttribute('aria-label'),
          pressed: button.getAttribute('aria-pressed')
        }
      })
    }
  })
  expect(geometry.topbarOverflow, 'topbar must not overflow horizontally').toBeLessThanOrEqual(1)
  expect(geometry.searchRight, 'functional search must finish before theme controls').toBeLessThanOrEqual(geometry.groupLeft + 0.5)
  expect(geometry.buttons).toHaveLength(6)
  for (const button of geometry.buttons) {
    expect(button.centerHit, `${button.key} center must receive the real pointer`).toBe(true)
    expect(button.width).toBeGreaterThanOrEqual(22)
    expect(button.height).toBeGreaterThanOrEqual(22)
    expect(button.label).toMatch(/^切换到.+主题$/)
    expect(button.pressed).toMatch(/^(true|false)$/)
  }
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1280, height: 800 }]) {
  test(`BasePortal six themes are real-clickable at ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    await openShell(page, viewport)
    await expect(page.locator('.bpl-cmdk--fn')).toBeVisible()
    await expect(page.locator('.bpl-cmdk--fn kbd')).toBeHidden()
    await expect(page.locator('.bpl-help__btn')).toBeVisible()
    await expect(page.locator('.bpl-bell')).toBeVisible()
    await assertTopbarGeometry(page)

    let dashboardRequests = 0
    page.on('request', (request) => {
      if (DASHBOARD_API.test(request.url())) dashboardRequests += 1
    })

    const layout = page.locator('.base-portal-layout')
    for (const key of THEMES) {
      const button = page.locator(`button.bpl-thdot--${key}`)
      await expect(button).toBeVisible()
      await button.click()
      await expect(layout).toHaveClass(new RegExp(`\\bth-${key}\\b`))
      await expect(button).toHaveAttribute('aria-pressed', 'true')
      await expect(page.locator('.bpl-thdot[aria-pressed="true"]')).toHaveCount(1)
    }
    expect(dashboardRequests, 'theme switching must not rebuild business requests').toBe(0)
    await capture(page, testInfo, `base-portal-themes-${viewport.width}x${viewport.height}`)
  })
}

test('BasePortal theme controls follow native Tab, Space and Enter behavior', async ({ page }, testInfo) => {
  await openShell(page, { width: 1366, height: 768 })
  const search = page.locator('.bpl-cmdk--fn input')
  await search.focus()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Tab')
  const first = page.locator('button.bpl-thdot--e')
  await expect(first).toBeFocused()
  await page.keyboard.press('Space')
  await expect(first).toHaveAttribute('aria-pressed', 'true')

  await page.keyboard.press('Tab')
  const second = page.locator('button.bpl-thdot--f')
  await expect(second).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(second).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.base-portal-layout')).toHaveClass(/\bth-f\b/)

  const focusOutline = await second.evaluate((element) => getComputedStyle(element).outlineStyle)
  expect(focusOutline).not.toBe('none')
  await capture(page, testInfo, 'base-portal-theme-keyboard-1366x768')
})
