import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

async function dismissGuide(page) {
  const masks = [
    page.locator('.app-step-guide__mask'),
    page.locator('.tour-mask')
  ]
  for (const mask of masks) {
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

async function setBatchStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

test.describe.serial('Golden rollout · representative business pages', () => {
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationFixture()
  })

  test('Student affairs dashboard · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dashboard`)

    await expect(page).toHaveURL(/\/admin\/student-affairs\/dashboard/)
    await expect(page.locator('.sa-summary-strip')).toBeVisible()
    await expect(page.locator('.sa-grid--priority')).toBeVisible()
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('body')).not.toContainText('正在加载学工看板真实数据…')

    await capture(page, testInfo, 'rollout-student-affairs-a')
  })

  test('Internship dashboard · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'internship.selectedBatchId', internshipFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship?batchId=${encodeURIComponent(internshipFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/internship/)
    await expect(page.locator('.idb-path')).toBeVisible()
    await expect(page.locator('#idb-batch-progress')).toBeVisible()
    await expect(page.locator('#idb-todos')).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/请先选择实习批次|存在多个进行中批次/)

    await capture(page, testInfo, 'rollout-internship-a')
  })

  test('Graduation dashboard · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/graduation?batchId=${encodeURIComponent(graduationFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/graduation/)
    await expect(page.locator('.gdb-page')).toBeVisible()
    await expect(page.locator('.gdb-command-bar')).toBeVisible()
    await expect(page.locator('.gdb-todos')).toBeVisible()
    await expect(page.locator('body')).not.toContainText('请先选择或创建毕设批次')

    await capture(page, testInfo, 'rollout-graduation-a')
  })
})
