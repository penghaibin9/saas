import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function openStaffWorkspace(page, api, path) {
  await page.addInitScript((token) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, api.token)
  await page.goto(`${config.staffBaseUrl}${path}`)
  await dismissGuide(page)
}

test.describe.serial('Golden rollout · message preferences / channel governance · Batch 16', () => {
  let adminApi

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
  })

  test('Message settings workspace · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/settings')

    await expect(page).toHaveURL(/\/admin\/messages\/settings/)
    await expect(page.getByRole('heading', { name: '消息设置', exact: true })).toBeVisible()
    await expect(page.locator('.mc-settings')).toBeVisible()
    await expect(page.locator('.mc-settings .mc-panel')).toHaveCount(4)
    await expect(page.getByText('分类偏好', { exact: true })).toBeVisible()
    await expect(page.getByText('渠道', { exact: true })).toBeVisible()
    await expect(page.getByText('静默时段', { exact: true })).toBeVisible()
    await expect(page.getByText('发布频控', { exact: true })).toBeVisible()

    const visual = await page.locator('.mc-settings').evaluate((el) => {
      const style = getComputedStyle(el)
      const panels = [...el.querySelectorAll('.mc-panel')]
      const first = panels[0]?.getBoundingClientRect()
      const second = panels[1]?.getBoundingClientRect()
      const panelStyle = panels[0] ? getComputedStyle(panels[0]) : null
      const note = el.querySelector('.mc-settings__note')
      return {
        display: style.display,
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height,
        columns: style.gridTemplateColumns.trim().split(/\s+/).length,
        firstTop: first?.top || 0,
        secondTop: second?.top || 0,
        secondLeft: second?.left || 0,
        firstLeft: first?.left || 0,
        panelRadius: panelStyle ? Number.parseFloat(panelStyle.borderTopLeftRadius) : 0,
        noteRadius: note ? Number.parseFloat(getComputedStyle(note).borderTopLeftRadius) : 0
      }
    })
    expect(visual.display).toBe('grid')
    expect(visual.width).toBeGreaterThanOrEqual(1000)
    expect(visual.width).toBeLessThanOrEqual(1060)
    expect(visual.height).toBeLessThanOrEqual(610)
    expect(visual.columns).toBe(2)
    expect(Math.abs(visual.firstTop - visual.secondTop)).toBeLessThanOrEqual(2)
    expect(visual.secondLeft - visual.firstLeft).toBeGreaterThan(450)
    expect(visual.panelRadius).toBeGreaterThanOrEqual(14)
    expect(visual.noteRadius).toBeGreaterThanOrEqual(9)

    await capture(page, testInfo, 'rollout-message-settings-b')
  })
})
