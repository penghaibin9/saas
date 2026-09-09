import { randomUUID } from 'node:crypto'
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

test.describe.serial('Golden rollout · Student Affairs funding workbench · Screenshot A', () => {
  let adminApi
  let project
  let batch
  let projectName

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
    const runId = String(rawRun).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
    // A retried worker reruns beforeAll: use independent names, not ambiguous duplicate options.
    projectName = `Playwright 助学金治理 ${runId}-${randomUUID().slice(0, 8)}`

    // Build only real governance context through formal production APIs.
    // No applicant, amount KPI or recipient is fabricated for visual evidence.
    project = await adminApi.post('/student-affairs/funding/projects', {
      projectName,
      projectType: 'GRANT',
      amount: 3000,
      quota: 10
    })
    expect(project?.projectId).toBeTruthy()

    batch = await adminApi.post('/student-affairs/funding/batches', {
      projectId: String(project.projectId),
      schoolYear: '2026-2027',
      publicityDays: 5,
      quota: 10,
      publish: true
    })
    expect(batch?.batchId).toBeTruthy()
  })

  test('real project and batch empty-state · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    const applicationsLoaded = page.waitForResponse(response => {
      const url = new URL(response.url())
      return url.pathname.endsWith('/student-affairs/funding/applications') &&
        url.searchParams.get('batchId') === String(batch.batchId) &&
        response.request().method() === 'GET'
    })
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/funding')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/funding/)
    await expect(page.getByRole('heading', { name: '申请评审', exact: true })).toBeVisible()
    const context = page.locator('.fd-ctxbar')
    await expect(context).toBeVisible()
    await context.getByRole('combobox').first().click()
    await page.getByRole('option', { name: `助学金 · ${projectName}`, exact: true }).click()
    await expect(context).toContainText(projectName)
    // Selecting a project does not prove a selected batch. Pin the actual API-created batch.
    await context.getByRole('combobox').nth(1).click()
    await page.getByRole('option').filter({ hasText: '2026-2027' }).click()
    const applicationsResponse = await applicationsLoaded
    expect(applicationsResponse.status()).toBe(200)
    expect((await applicationsResponse.json()).code).toBe(0)
    await expect(context).toContainText('2026-2027')
    await expect(page.locator('.fd-toolbar')).toBeVisible()
    await expect(page.locator('.fd-workspace')).toBeVisible()
    await expect(page.locator('.fd-list')).toContainText('该批次暂无申请')
    await expect(page.locator('.fd-detail')).toHaveCount(0)
    const [listBox, workspaceBox] = await Promise.all([
      page.locator('.fd-list').boundingBox(), page.locator('.fd-workspace').boundingBox()
    ])
    expect(listBox.width).toBeGreaterThan(workspaceBox.width * 0.95)
    await expect(context.getByRole('button', { name: '受理申请', exact: true })).toBeEnabled()

    await capture(page, testInfo, 'rollout-student-affairs-funding-a')
  })
})
