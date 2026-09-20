import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'
import { WORKSPACE_THEMES } from '../../frontend/src/components/workspace/teacherWorkspace.js'

const rgb = hex => `rgb(${hex.slice(1).match(/../g).map(value => parseInt(value, 16)).join(', ')})`
function luminance(value) {
  const channels = value.match(/[\d.]+/g)?.slice(0, 3).map(Number)
  if (!channels || channels.length !== 3) throw new Error(`Unexpected computed color: ${value}`)
  return channels.reduce((sum, channel, index) => {
    const value = channel / 255
    return sum + [0.2126, 0.7152, 0.0722][index] * (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
  }, 0)
}
function contrast(foreground, background) {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return (light + 0.05) / (dark + 0.05)
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
async function openAppearance(page) {
  const dialog = page.locator('.graduation-portal .tw-dialog')
  if (!await dialog.isVisible()) {
    await page.getByTitle('查看账号与切换身份', { exact: true }).click()
    await page.getByRole('region', { name: '账户与身份', exact: true })
      .getByRole('button', { name: /^外观设置/ }).click()
  }
  await expect(dialog).toBeVisible()
  return dialog
}

test.describe('Graduation batch presentation in the unchanged shared workspace', () => {
  test.setTimeout(120_000)
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  test('all existing workspace themes remain readable without changing the selected batch or route', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const url = new URL('/admin/graduation', config.staffBaseUrl)
    url.searchParams.set('batchId', String(fixture.batchId))
    await page.goto(url.toString())
    await dismissGuide(page)
    await expect(page.locator('.graduation-portal.bpl-workspace .tw-frame')).toHaveCount(1)
    const strip = page.locator('.graduation-portal .gbs')
    await expect(strip).toHaveCount(1)
    const select = strip.getByRole('combobox', { name: '选择毕设批次', exact: true })
    await expect(select).toHaveValue(String(fixture.batchId))
    await expect(page.locator('.gd-business-view h1:visible')).toHaveCount(1)
    const originalRoute = routeState(page)
    const dialog = await openAppearance(page)
    const initialTheme = await dialog.locator('.tw-themes button[aria-pressed="true"] strong').innerText()
    const measurements = []
    try {
      for (const theme of WORKSPACE_THEMES) {
        await openAppearance(page)
        const choice = dialog.getByRole('button', { name: theme.label, exact: true })
        await choice.click()
        await expect(choice).toHaveAttribute('aria-pressed', 'true')
        await expect.poll(() => select.evaluate(element => {
          const style = getComputedStyle(element)
          return { background: style.backgroundColor, foreground: style.color }
        })).toEqual({ background: rgb(theme.header), foreground: rgb(theme.ink) })
        await dialog.getByRole('button', { name: '关闭外观设置', exact: true }).click()
        await expect(dialog).toBeHidden()
        await expect(select).toHaveValue(String(fixture.batchId))
        expect(routeState(page)).toEqual(originalRoute)
        const size = await select.evaluate(element => {
          const style = getComputedStyle(element)
          return { foreground: style.color, background: style.backgroundColor, fontSize: parseFloat(style.fontSize), height: element.getBoundingClientRect().height }
        })
        expect(size.fontSize).toBeGreaterThanOrEqual(13)
        expect(size.height).toBeGreaterThanOrEqual(34)
        const ratio = contrast(size.foreground, size.background)
        expect(ratio, `${theme.label}: batch field contrast`).toBeGreaterThanOrEqual(4.5)
        measurements.push({ theme: theme.key, ...size, contrast: ratio })
        await page.screenshot({ path: testInfo.outputPath(`graduation-batch-theme-${theme.key}.png`), fullPage: false, animations: 'disabled' })
      }
      expect(measurements).toHaveLength(WORKSPACE_THEMES.length)
    } finally {
      // This is a real UI setting in an isolated browser context, not an API stub.
      await openAppearance(page)
      await dialog.getByRole('button', { name: initialTheme, exact: true }).click()
      await dialog.getByRole('button', { name: '关闭外观设置', exact: true }).click()
      await testInfo.attach('graduation-batch-theme-evidence', {
        body: Buffer.from(JSON.stringify({ head: process.env.E2E_EXPECTED_SHA || null, measurements }, null, 2)),
        contentType: 'application/json'
      })
    }
  })
})
