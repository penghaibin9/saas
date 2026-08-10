import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

async function dismissPageGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: '跳过引导' }).click()
    await expect(mask).toBeHidden()
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function captureGolden(page, testInfo, name) {
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)

  await page.screenshot({
    path: viewportPath,
    fullPage: false,
    animations: 'disabled',
    caret: 'hide'
  })
  await page.screenshot({
    path: fullPath,
    fullPage: true,
    animations: 'disabled',
    caret: 'hide'
  })

  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

test.describe.serial('Golden PC visual evidence', () => {
  test('Workbench · 1440x1000 success-state evidence', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/workbench`)

    await expect(page.locator('.wb-v2__hero')).toBeVisible()
    await expect(page.locator('.wb-v2__action-grid')).toBeVisible()
    await expect(page.locator('.wb-v2__headline')).not.toContainText(/正在读取|暂时未能加载/)
    await dismissPageGuide(page)

    await captureGolden(page, testInfo, 'golden-workbench-b')
  })

  test('Student master · 1440x1000 success-state evidence', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student/list`)

    await expect(page).toHaveURL(/\/admin\/student\/list/)
    await expect(page.locator('.sl-voided-toggle')).toBeVisible()
    await expect(page.locator('body')).not.toContainText('暂无学生主档访问权限')
    await expect(page.locator('body')).not.toContainText('正在加载数据…')

    await captureGolden(page, testInfo, 'golden-student-master-b')
  })

  test('Selection console · 1440x1000 success-state evidence', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.multiRole)
    await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)

    await expect(page).toHaveURL(/\/admin\/academic-affairs\/selection/)
    await expect(page.locator('.aasel-layout')).toBeVisible()
    await expect(page.locator('.aasel-list-card')).toBeVisible()
    await expect(page.locator('body')).not.toContainText('正在加载数据…')

    await captureGolden(page, testInfo, 'golden-selection-console-b')
  })
})
