import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'

const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'

async function loginTeacherMini(page) {
  await page.goto(`${miniBase}/#/pages/login/teacher/index`)
  await page.locator('input[placeholder="工号 / 手机号"]').fill(config.mentor.username)
  await page.locator('input[placeholder="密码"]').fill(config.mentor.password)
  await page.getByText('填写', { exact: true }).click()
  await page.locator('input[placeholder="请输入学校编码"]').fill(config.mentor.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByRole('button', { name: '进入教师工作台' }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 10_000 })
}

async function settle(page) {
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.waitForTimeout(300)
}

async function assertMobileFit(page) {
  const fit = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth
  }))
  expect(fit.scrollWidth, `document overflow at ${fit.width}px`).toBeLessThanOrEqual(fit.width + 1)
  expect(fit.bodyWidth, `body overflow at ${fit.width}px`).toBeLessThanOrEqual(fit.width + 1)
}

async function capture(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await settle(page)
  await assertMobileFit(page)
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
}

function pagedGraduationResponse(page, suffix) {
  return page.waitForResponse((response) => {
    const url = response.url()
    return response.ok()
      && response.request().method() === 'GET'
      && url.includes(`/api/v1/mobile/teacher/graduation/${suffix}`)
  }, { timeout: 15_000 })
}

function assertPagedBatchUrl(response, label) {
  const url = new URL(response.url())
  const batchId = url.searchParams.get('batchId')
  expect(batchId, `${label} must carry exact batchId`).toMatch(/^\d+$/)
  expect(url.searchParams.get('page'), `${label} page`).toBe('1')
  expect(url.searchParams.get('pageSize'), `${label} pageSize`).toBe('20')
  return batchId
}

test.describe.serial('V9.2 U8 · teacher miniapp graduation Gold evidence', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('teacher graduation workbench and taskbook fit 390/375 with real paged API batch context', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await loginTeacherMini(page)

    const guideRequest = pagedGraduationResponse(page, 'midterm/queue')
    await page.goto(`${miniBase}/#/pages/teacher/graduation-guide/index`)
    const guideResponse = await guideRequest
    const guideBatchId = assertPagedBatchUrl(guideResponse, 'graduation guide')
    await expect(page.getByText('批阅', { exact: false }).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('中期', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('成绩', { exact: false }).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/真实接口不可用|网络不稳定，开发演示数据/)

    await capture(page, testInfo, 'gd-U8-teacher-workbench-B', 390, 844)
    await capture(page, testInfo, 'gd-U8-teacher-workbench-B', 375, 812)

    const taskbookRequest = pagedGraduationResponse(page, 'taskbooks')
    await page.goto(`${miniBase}/#/pages/teacher/graduation-taskbook/index`)
    const taskbookResponse = await taskbookRequest
    const taskbookBatchId = assertPagedBatchUrl(taskbookResponse, 'taskbook')
    expect(taskbookBatchId, 'guide/taskbook must use the same selected batch').toBe(guideBatchId)
    await expect(page.getByText('毕设任务书', { exact: true })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/任务书列表/).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/真实接口不可用|网络不稳定，开发演示数据/)

    await capture(page, testInfo, 'gd-U8-taskbook-B', 390, 844)
    await capture(page, testInfo, 'gd-U8-taskbook-B', 375, 812)

    const metaPath = testInfo.outputPath('gd-U8-teacher-mobile-B-meta.json')
    await fs.writeFile(metaPath, JSON.stringify({
      phase: 'B', card: 'U8', head: process.env.GITHUB_SHA || 'local',
      fixtureBatchId: fixture.batchId, selectedBatchId: guideBatchId,
      mentor: config.mentor.username,
      pages: ['graduation-guide', 'graduation-taskbook'],
      viewports: [{ width: 390, height: 844 }, { width: 375, height: 812 }]
    }, null, 2), 'utf8')
    await testInfo.attach('gd-U8-teacher-mobile-B-meta', { path: metaPath, contentType: 'application/json' })
  })
})
