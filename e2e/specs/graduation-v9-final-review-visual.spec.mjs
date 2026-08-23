import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { captureGoldCandidate, dynamicTextMasks, goldEnvironment } from '../lib/graduation-gold.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const BACKEND_DIR = fileURLToPath(new URL('../../backend/', import.meta.url))

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function expectBrowserApiSuccess(response, action) {
  const body = await response.json()
  expect(response.ok(), `${action} HTTP ${response.status()}: ${JSON.stringify(body).slice(0, 800)}`).toBeTruthy()
  expect(body.code, `${action} business error: ${JSON.stringify(body).slice(0, 800)}`).toBe(0)
  return body.data
}

function buildPreviewablePdf(label) {
  const safeLabel = String(label).replace(/[()\\]/g, '')
  const stream = `BT /F1 14 Tf 54 720 Td (YUEKE E2E ${safeLabel}) Tj ET\n`
  const objects = [
    null,
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [4 0 R] /Count 1 >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>',
    `<< /Length ${Buffer.byteLength(stream, 'ascii')} >>\nstream\n${stream}endstream`,
  ]
  let body = '%PDF-1.4\n%YUEKE E2E SYNTHETIC DOCUMENT\n'
  const offsets = [0]
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = Buffer.byteLength(body, 'ascii')
    body += `${id} 0 obj\n${objects[id]}\nendobj\n`
  }
  const xrefOffset = Buffer.byteLength(body, 'ascii')
  body += `xref\n0 ${objects.length}\n0000000000 65535 f \n`
  for (let id = 1; id < objects.length; id += 1) {
    body += `${String(offsets[id]).padStart(10, '0')} 00000 n \n`
  }
  body += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  return Buffer.from(body, 'ascii')
}

async function expectDecisionAboveFold(page) {
  const viewport = page.viewportSize()
  expect(viewport).toBeTruthy()
  const review = page.locator('.gd-review-workspace__review')
  const targets = [
    ['安全版本', review.getByText('当前安全版本', { exact: true })],
    ['SHA', review.getByText(/SHA=/).first()],
    ['通过当前版本', page.getByRole('button', { name: /通过当前版本/ })],
    ['退回当前版本', page.getByRole('button', { name: /退回当前版本/ })]
  ]
  for (const [label, locator] of targets) {
    await expect(locator, `${label} must be visible`).toBeVisible()
    const box = await locator.boundingBox()
    expect(box, `${label} must have a rendered box`).toBeTruthy()
    expect(box.x >= 0, `${label} must start inside the viewport width`).toBeTruthy()
    expect(box.x + box.width <= viewport.width, `${label} must stay inside the ${viewport.width}px viewport width`).toBeTruthy()
    expect(box.y >= 0, `${label} must start inside the viewport`).toBeTruthy()
    expect(box.y + box.height <= viewport.height, `${label} must stay above the ${viewport.height}px fold`).toBeTruthy()
  }
}

async function attachScreenshot(page, testInfo, name, width, height, goldMasks = []) {
  await page.setViewportSize({ width, height })
  await dismissGuide(page)
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  await expectDecisionAboveFold(page)
  const output = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path: output, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path: output, contentType: 'image/png' })
  await captureGoldCandidate(page, testInfo, {
    name: name.replace('-B', '-GoldCandidate'), width, height, masks: goldMasks,
  })
}

test.describe.serial('V9.2 U3 · final review production visual', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('real final/FileVersion review workspace · Screenshot B 1440 + 1280', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentGraduationPage(page, config.studentBaseUrl)
    await student.open()
    await student.signTaskbookIfNeeded()

    // The full interaction suite may already have completed the same run-scoped
    // proposal before this visual test starts. Reuse that canonical state instead
    // of trying to submit an already-approved proposal a second time.
    const proposalStep = student.step('开题')
    const alreadyApproved = await proposalStep.getByText(/已通过|通过/).count() > 0
    if (!alreadyApproved) {
      await student.submitProposal({
        suffix: `${fixture.runId}-u3`,
        fileName: `u3-proposal-${fixture.runId}.pdf`
      })

      await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
      const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
      await staff.openProposals('PENDING_REVIEW')
      await staff.selectStudent()
      await staff.approve()
    }

    execFileSync(
      'python',
      ['scripts/e2e_seed_graduation_final_prerequisite.py', fixture.gdStudentId],
      {
        cwd: BACKEND_DIR,
        env: { ...process.env, PYTHONPATH: BACKEND_DIR },
        encoding: 'utf8'
      }
    )

    // Re-enter through the real student UI after the isolated prerequisite update.
    // The file upload and final submit below both travel through the production
    // student-portal request layer; no final/file/review record is seeded here.
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await student.open()
    const finalStep = page.locator('.gd-step').filter({
      has: page.getByRole('heading', { name: /成果/ })
    }).first()
    await expect(finalStep).toBeVisible()

    // A Playwright retry reuses this run's isolated MySQL database. If the first
    // attempt already completed the real upload + submit and only the later visual
    // assertion failed, the canonical final is now pending review. Reuse that state
    // rather than creating a duplicate final/FileVersion on retry.
    const finalStateText = await finalStep.innerText()
    const alreadySubmitted = /待.*审|已提交/.test(finalStateText)
    if (!alreadySubmitted) {
      let fileInput = finalStep.locator('input[type=file]')
      if (!(await fileInput.count())) {
        const openFinal = finalStep.getByRole('button').filter({ hasText: /提交|修改|重交|完善|成果/ }).first()
        await expect(openFinal).toBeVisible()
        await openFinal.click()
        fileInput = finalStep.locator('input[type=file]')
      }
      await expect(fileInput).toHaveCount(1)

      const uploadResponsePromise = page.waitForResponse((response) => {
        const target = new URL(response.url())
        return response.request().method() === 'POST' && target.pathname.endsWith('/files')
      })
      await fileInput.setInputFiles({
        name: `u3-final-${fixture.runId}.pdf`,
        mimeType: 'application/pdf',
        buffer: buildPreviewablePdf(`${fixture.runId}-u3-final`)
      })
      const uploaded = await expectBrowserApiSuccess(await uploadResponsePromise, '学生上传成果文件')
      expect(uploaded?.fileId).toBeTruthy()

      const submitFinal = finalStep.getByRole('button', { name: /提交论文成果/ })
      await expect(submitFinal).toBeEnabled()
      const [submitResponse] = await Promise.all([
        page.waitForResponse((response) =>
          response.request().method() === 'POST' && response.url().includes('/portal/graduation/final/submit')
        ),
        submitFinal.click()
      ])
      const submitted = await expectBrowserApiSuccess(submitResponse, '学生提交论文成果')
      expect(submitted?.status).toBe('PENDING_REVIEW')
    } else {
      expect(finalStateText).toMatch(/待.*审|已提交/)
    }

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '成果检查', exact: true })).toBeVisible()
    const workspace = page.locator('.gd-review-workspace')
    const queue = workspace.locator('.gd-review-workspace__queue')
    const document = workspace.locator('.gd-review-workspace__document')
    const review = workspace.locator('.gd-review-workspace__review')
    await expect(workspace).toBeVisible()
    await expect(queue).toContainText(fixture.topicTitle)
    await expect(document).toContainText(fixture.topicTitle)
    await expect(review).toContainText('当前安全版本')
    await expect(review).toContainText(/SHA=|安全门/)
    await expect(review).toContainText('查重')
    await expect(page.getByRole('button', { name: /通过当前版本/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /退回当前版本/ })).toBeVisible()

    const goldMasks = [
      page.locator('.gbs__select'),
      ...dynamicTextMasks(page, [fixture.runId, fixture.batchName, fixture.topicTitle]),
    ]
    await attachScreenshot(page, testInfo, 'gd-U3-final-B', 1440, 900, goldMasks)
    await attachScreenshot(page, testInfo, 'gd-U3-final-B', 1280, 800, goldMasks)

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
      fixtureVersion: {
        runId: fixture.runId,
        gdStudentId: fixture.gdStudentId,
        studentNo: fixture.studentNo,
      },
      browserProject: environment.browserProject,
      deviceScaleFactor: environment.deviceScaleFactor,
      language: environment.language,
      fontEnvironment: environment.fontEnvironment,
      dynamicZones: ['security-watermark', 'run-scoped-batch-label', 'run-scoped-topic-title'],
      viewports: [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]
    }, null, 2), 'utf8')
    await testInfo.attach('gd-U3-final-B-meta', { path: metaPath, contentType: 'application/json' })
  })
})
