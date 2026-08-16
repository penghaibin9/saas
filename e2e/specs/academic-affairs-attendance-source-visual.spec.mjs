import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function dismissPageGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: '跳过引导' }).click()
    await expect(mask).toBeHidden()
  }
}

async function captureViewport(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
}

test.describe.serial('Academic C attendance source visual contract', () => {
  test('formal attendance stays default and ADMIN_SPECIAL is visibly isolated', async ({ page }, testInfo) => {
    await loginAcademicAdmin(page)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/attendance-stats`)
    await expect(page).toHaveURL(/\/admin\/academic-affairs\/attendance-stats/)
    await dismissPageGuide(page)

    await expect(page.getByRole('heading', { name: '课堂考勤统计' })).toBeVisible()
    await expect(page.getByText('默认汇总只统计正式课堂', { exact: false })).toBeVisible()
    await expect(page.getByText('当前汇总口径：', { exact: false })).toContainText('正式课堂')
    await expect(page.getByRole('button', { name: '旷课预警扫描' })).toBeVisible()

    const sourceSelect = page.locator('select:has(option[value="ADMIN_SPECIAL"])')
    await expect(sourceSelect).toHaveCount(1)
    await sourceSelect.selectOption('ADMIN_SPECIAL')

    await expect(page.getByText('特殊补录仅用于审计核对，不进入标准课堂旷课预警。', { exact: true })).toBeVisible()
    await expect(page.getByText('当前汇总口径：', { exact: false })).toContainText('管理员特殊补录')
    await expect(page.getByRole('button', { name: '旷课预警扫描' })).toHaveCount(0)
    await expect(page.getByText('ADMIN_SPECIAL', { exact: true })).toHaveCount(0)

    await captureViewport(page, testInfo, 'academic-c-attendance-admin-special', 1280, 720)
    await captureViewport(page, testInfo, 'academic-c-attendance-admin-special', 1440, 900)
    await captureViewport(page, testInfo, 'academic-c-attendance-admin-special', 1920, 1080)

    await sourceSelect.selectOption('')
    await expect(page.getByText('当前汇总口径：', { exact: false })).toContainText('正式课堂')
    await expect(page.getByRole('button', { name: '旷课预警扫描' })).toBeVisible()
  })
})
