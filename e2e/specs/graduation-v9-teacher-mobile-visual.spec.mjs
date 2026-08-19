import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { prepareGraduationTeacherMobileGoldFixture, u8TeacherAccount } from '../lib/graduation-u8-fixture.mjs'
import { captureGoldCandidate, dynamicTextMasks, goldEnvironment } from '../lib/graduation-gold.mjs'

const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'

async function loginTeacherMini(page) {
  await page.goto(`${miniBase}/#/pages/login/teacher/index`)
  const loginFields = page.getByRole('textbox')
  await loginFields.nth(0).fill(u8TeacherAccount.username)
  await loginFields.nth(1).fill(u8TeacherAccount.password)
  await page.getByText('填写', { exact: true }).click()
  await loginFields.nth(2).fill(u8TeacherAccount.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
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

async function capture(page, testInfo, name, width, height, goldMasks = [], visualErrors = []) {
  await page.setViewportSize({ width, height })
  await settle(page)
  await assertMobileFit(page)
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
  try {
    await captureGoldCandidate(page, testInfo, {
      name: name.replace('-B', '-GoldCandidate'), width, height, masks: goldMasks,
    })
  } catch (error) {
    visualErrors.push(`${name} ${width}x${height}: ${error?.stack || error?.message || error}`)
  }
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
    fixture = await prepareGraduationTeacherMobileGoldFixture()
  })

  test('teacher graduation workbench and taskbook fit 390/375 with real paged API batch context', async ({ page }, testInfo) => {
    const visualErrors = []
    await page.setViewportSize({ width: 390, height: 844 })
    await loginTeacherMini(page)

    const guideRequest = pagedGraduationResponse(page, 'midterm/queue')
    await page.goto(`${miniBase}/#/pages/teacher/graduation-guide/index`)
    const guideResponse = await guideRequest
    const guideBatchId = assertPagedBatchUrl(guideResponse, 'graduation guide')
    expect(guideBatchId, 'graduation guide must use the deterministic U8 fixture batch').toBe(fixture.batchId)
    await expect(page.getByText('批阅', { exact: false }).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('中期', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('成绩', { exact: false }).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/真实接口不可用|网络不稳定，开发演示数据/)

    const guideMasks = dynamicTextMasks(page, [fixture.runId, fixture.batchName, fixture.topicTitle])
    await capture(page, testInfo, 'gd-U8-teacher-workbench-B', 390, 844, guideMasks, visualErrors)
    await capture(page, testInfo, 'gd-U8-teacher-workbench-B', 375, 812, guideMasks, visualErrors)

    const taskbookRequest = pagedGraduationResponse(page, 'taskbooks')
    await page.goto(`${miniBase}/#/pages/teacher/graduation-taskbook/index`)
    const taskbookResponse = await taskbookRequest
    const taskbookBatchId = assertPagedBatchUrl(taskbookResponse, 'taskbook')
    expect(taskbookBatchId, 'guide/taskbook must use the same selected batch').toBe(guideBatchId)
    await expect(page.getByText('毕设任务书', { exact: true })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/任务书列表/).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/真实接口不可用|网络不稳定，开发演示数据/)

    const taskbookMasks = dynamicTextMasks(page, [fixture.runId, fixture.batchName, fixture.topicTitle])
    await capture(page, testInfo, 'gd-U8-taskbook-B', 390, 844, taskbookMasks, visualErrors)
    await capture(page, testInfo, 'gd-U8-taskbook-B', 375, 812, taskbookMasks, visualErrors)

    const environment = await goldEnvironment(page, testInfo)
    const metaPath = testInfo.outputPath('gd-U8-teacher-mobile-B-meta.json')
    await fs.writeFile(metaPath, JSON.stringify({
      phase: 'B',
      card: 'U8',
      head: environment.goldHead,
      goldHead: environment.goldHead,
      tenant: u8TeacherAccount.tenant,
      role: 'GD_MENTOR',
      fixtureBatchId: fixture.batchId,
      selectedBatchId: guideBatchId,
      fixtureVersion: { runId: fixture.runId, gdStudentId: fixture.gdStudentId, studentNo: fixture.studentNo },
      mentor: u8TeacherAccount.username,
      routes: [
        '#/pages/teacher/graduation-guide/index',
        '#/pages/teacher/graduation-taskbook/index'
      ],
      browserProject: environment.browserProject,
      deviceScaleFactor: environment.deviceScaleFactor,
      language: environment.language,
      fontEnvironment: environment.fontEnvironment,
      dynamicZones: ['run-scoped-batch-label', 'run-scoped-topic-title'],
      pages: ['graduation-guide', 'graduation-taskbook'],
      viewports: [{ width: 390, height: 844 }, { width: 375, height: 812 }]
    }, null, 2), 'utf8')
    await testInfo.attach('gd-U8-teacher-mobile-B-meta', { path: metaPath, contentType: 'application/json' })

    if (visualErrors.length) {
      throw new Error(`U8 Gold visual mismatches (${visualErrors.length}):\n\n${visualErrors.join('\n\n')}`)
    }
  })
})