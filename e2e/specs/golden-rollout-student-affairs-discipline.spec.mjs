import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, items } from '../lib/api-fixture.mjs'

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

test.describe.serial('Golden rollout · Student Affairs discipline workbench · Screenshot A', () => {
  let adminApi
  let caseRow
  let reason

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
    const runId = String(rawRun).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
    reason = `Playwright 隔离处分事实核验 ${runId}`

    const data = await adminApi.get('/students', { keyword: config.student.username, page: 1, pageSize: 50 })
    const student = items(data).find((row) => String(row.studentNo || row.loginName || '') === config.student.username)
    expect(student?.id || student?.studentId).toBeTruthy()

    // Register one real case through the formal production endpoint. Keep it at
    // REGISTERED: this screenshot audits the operational record without advancing
    // approval, effective-state projection or any other business lifecycle.
    caseRow = await adminApi.post('/student-affairs/discipline/cases', {
      studentId: String(student.id || student.studentId),
      discType: 'WARNING',
      reason,
      docNo: `PW-${runId}`
    })
    expect(caseRow?.caseId).toBeTruthy()
  })

  test('real registered case · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/discipline')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/discipline/)
    await expect(page.getByRole('heading', { name: '违纪处分工作台', exact: true })).toBeVisible()
    await expect(page.locator('.dp-toolbar')).toBeVisible()
    await expect(page.locator('.dp-workspace')).toBeVisible()

    const item = page.locator('.dp-qitem').filter({ hasText: reason }).first()
    await expect(item).toBeVisible()
    await item.click()
    await expect(page.locator('.dp-detail')).toContainText(reason)
    await expect(page.locator('.dp-detail')).toContainText(`PW-${runId}`)

    await capture(page, testInfo, 'rollout-student-affairs-discipline-a')
  })
})
