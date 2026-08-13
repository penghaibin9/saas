import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
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

async function uploadGraduationPdf(api, fileName) {
  const form = new FormData()
  form.append('file', new File([
    '%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<<>>\n%%EOF\n'
  ], fileName, { type: 'application/pdf' }))
  const target = new URL(`${config.apiBaseUrl}/files`)
  target.searchParams.set('bizType', 'GRADUATION_MATERIAL')
  const response = await fetch(target, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${api.token}`,
      'X-Forwarded-For': '10.255.0.31'
    },
    body: form
  })
  const body = await response.json()
  expect(response.ok(), JSON.stringify(body)).toBeTruthy()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.fileId).toBeTruthy()
  return String(body.data.fileId)
}

async function attachScreenshot(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await dismissGuide(page)
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  const output = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path: output, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path: output, contentType: 'image/png' })
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

    const studentApi = await loginApi(config.student)
    const fileId = await uploadGraduationPdf(studentApi, `u3-final-${fixture.runId}.pdf`)
    const submitted = await studentApi.post('/mobile/graduation/final', {
      finalType: '初稿',
      attachments: [fileId]
    })
    expect(submitted.status).toBe('PENDING_REVIEW')

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '成果检查', exact: true })).toBeVisible()
    await expect(page.locator('.fr-split')).toBeVisible()
    await expect(page.locator('.fr-list')).toContainText(fixture.topicTitle)
    await expect(page.locator('.fr-pane')).toContainText(fixture.topicTitle)
    await expect(page.locator('.fr-pane')).toContainText('当前安全版本')
    await expect(page.locator('.fr-pane')).toContainText(/SHA-256|安全门/)
    await expect(page.locator('.fr-pane')).toContainText('查重')
    await expect(page.getByRole('button', { name: /通过当前版本/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /退回当前版本/ })).toBeVisible()

    await attachScreenshot(page, testInfo, 'gd-U3-final-B', 1440, 900)
    await attachScreenshot(page, testInfo, 'gd-U3-final-B', 1280, 800)
  })
})
