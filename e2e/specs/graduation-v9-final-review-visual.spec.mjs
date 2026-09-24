import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { captureGoldCandidate, dynamicTextMasks, goldEnvironment } from '../lib/graduation-gold.mjs'
import {
  dismissGraduationGuide,
  ensureFinalPending,
  expectRenderedPdfCanvas
} from '../lib/graduation-scenario-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 }
]

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function expectDecisionAboveFold(page) {
  const viewport = page.viewportSize()
  expect(viewport).toBeTruthy()
  const review = page.locator('.gd-review-workspace__review')
  const targets = [
    ['审核命令合同', review.locator('[data-testid="review-command-contract"]')],
    ['提交版本', review.getByText('提交版本', { exact: true })],
    ['文件版本', review.getByText('文件版本', { exact: true })],
    ['文件状态', review.getByText('文件状态', { exact: true })],
    ['文件证据入口', review.locator('.gd-review-workspace__evidence > summary')],
    ['通过当前版本', review.getByRole('button', { name: /通过当前版本/ })],
    ['退回当前版本', review.getByRole('button', { name: /退回当前版本/ })]
  ]
  for (const [label, locator] of targets) {
    await expect(locator, `${label} must be visible`).toBeVisible()
    const box = await locator.boundingBox()
    expect(box, `${label} must have a rendered box`).toBeTruthy()
    expect(box.x >= 0, `${label} must start inside viewport`).toBeTruthy()
    expect(box.x + box.width <= viewport.width, `${label} must stay inside viewport width`).toBeTruthy()
    expect(box.y >= 0, `${label} must start inside viewport`).toBeTruthy()
    expect(box.y + box.height <= viewport.height, `${label} must stay above fold`).toBeTruthy()
  }
}

async function capture(page, testInfo, fixture, width, height) {
  await page.setViewportSize({ width, height })
  await dismissGraduationGuide(page)
  await settleVisual(page)
  await expectDecisionAboveFold(page)

  const screenshot = testInfo.outputPath(`gd-U3-final-B-${width}x${height}.png`)
  await page.screenshot({ path: screenshot, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`gd-U3-final-B-${width}x${height}`, { path: screenshot, contentType: 'image/png' })

  await captureGoldCandidate(page, testInfo, {
    name: 'gd-U3-final-GoldCandidate',
    width,
    height,
    masks: [
      page.locator('.gbs__select'),
      ...dynamicTextMasks(page, [fixture.runId, fixture.batchName, fixture.topicTitle])
    ]
  })
}

test.describe.serial('V9.2 U3 · final review production visual', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('real final/FileVersion review workspace · Screenshot B 1440 + 1280', async ({ page }, testInfo) => {
    test.setTimeout(8 * 60_000)
    await page.setViewportSize(VIEWPORTS[0])
    await ensureFinalPending(page, fixture, {
      suffix: `u3-${testInfo.retry || 0}`,
      documentPages: 20
    })

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
    await dismissGraduationGuide(page)

    await expect(page.getByRole('heading', { name: '成果检查', exact: true })).toBeVisible()
    const workspace = page.locator('.gd-review-workspace')
    const queue = workspace.locator('.gd-review-workspace__queue')
    const document = workspace.locator('.gd-review-workspace__document')
    const review = workspace.locator('.gd-review-workspace__review')
    await expect(workspace).toBeVisible()
    await expect(queue).toContainText(fixture.topicTitle)
    await expect(document).toContainText(fixture.topicTitle)
    await expect(review.locator('[data-testid="review-command-contract"]')).toBeVisible()
    await expect(review).toContainText('提交版本')
    await expect(review).toContainText('文件版本')
    await expect(review).toContainText('文件状态')
    await expect(review.locator('.gd-review-workspace__evidence > summary')).toBeVisible()
    await expect(review).toContainText('SHA-256')
    await expect(review).toContainText('查重')
    await expect(review.getByRole('button', { name: /通过当前版本/ })).toBeVisible()
    await expect(review.getByRole('button', { name: /退回当前版本/ })).toBeVisible()
    await expectRenderedPdfCanvas(page)

    const failures = []
    for (const viewport of VIEWPORTS) {
      try {
        await capture(page, testInfo, fixture, viewport.width, viewport.height)
      } catch (error) {
        failures.push(`${viewport.width}x${viewport.height}: ${error instanceof Error ? error.message : String(error)}`)
      }
    }

    const environment = await goldEnvironment(page, testInfo)
    const metaPath = testInfo.outputPath('gd-U3-final-B-meta.json')
    await fs.writeFile(metaPath, JSON.stringify({
      phase: 'B',
      card: 'U3',
      head: environment.goldHead,
      goldHead: environment.goldHead,
      tenant: config.mentor.tenant,
      role: 'GD_MENTOR',
      batchId: fixture.batchId,
      route: `/admin/graduation/finals?batchId=${fixture.batchId}&tab=PENDING_REVIEW`,
      scenarioFactory: 'graduation-scenario-fixture.ensureFinalPending',
      fixtureVersion: {
        runId: fixture.runId,
        gdStudentId: fixture.gdStudentId,
        studentNo: fixture.studentNo,
        documentPages: 20
      },
      browserProject: environment.browserProject,
      deviceScaleFactor: environment.deviceScaleFactor,
      language: environment.language,
      fontEnvironment: environment.fontEnvironment,
      dynamicZones: ['security-watermark', 'run-scoped-batch-label', 'run-scoped-topic-title'],
      viewports: VIEWPORTS
    }, null, 2), 'utf8')
    await testInfo.attach('gd-U3-final-B-meta', { path: metaPath, contentType: 'application/json' })
    expect(failures, 'all U3 Gold Candidate viewports must match').toEqual([])
  })
})
