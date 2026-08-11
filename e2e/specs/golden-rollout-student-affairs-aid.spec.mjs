import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'

const DESKTOP = { width: 1440, height: 1000 }

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

test.describe.serial('Golden rollout · Student Affairs aid workbench · Screenshot A', () => {
  let adminApi
  let batch
  let batchName

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
    const runId = String(rawRun).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
    batchName = `Playwright 困难认定 ${runId}`

    // Real production API fact in the isolated E2E tenant. Do not fabricate
    // student/KPI state: a real empty batch is enough to audit this workbench.
    batch = await adminApi.post('/student-affairs/aid/batches', {
      batchName,
      schoolYear: '2026-2027',
      publicityDays: 5,
      publish: true
    })
    expect(batch?.batchId).toBeTruthy()
  })

  test('real batch empty-state · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/aid')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/aid/)
    await expect(page.getByRole('heading', { name: '困难认定工作台', exact: true })).toBeVisible()
    await expect(page.locator('.ad-batchbar')).toBeVisible()
    await expect(page.locator('.ad-toolbar')).toBeVisible()
    await expect(page.locator('.ad-workspace')).toBeVisible()
    await expect(page.locator('.ad-batchbar')).toContainText(batchName)
    await expect(page.locator('.ad-list')).toContainText('该批次暂无申请')
    await expect(page.locator('.ad-detail')).toContainText('请从左侧选择一条申请')

    await capture(page, testInfo, 'rollout-student-affairs-aid-a')
  })
})
