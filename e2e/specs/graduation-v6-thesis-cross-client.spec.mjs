import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const BACKEND_DIR = fileURLToPath(new URL('../../backend/', import.meta.url))
const MINI_BASE = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'
const TEACHER_BATCH_KEY = 'gx_gd_teacher_batch_v1'

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function expectBusinessSuccess(response, action) {
  const body = await response.json()
  expect(response.ok(), `${action} HTTP ${response.status()}: ${JSON.stringify(body).slice(0, 800)}`).toBeTruthy()
  expect(body.code, `${action} business error: ${JSON.stringify(body).slice(0, 800)}`).toBe(0)
  return body.data
}

function buildPreviewablePdf(label) {
  const safeLabel = String(label).replace(/[()\\]/g, '')
  const stream = `BT /F1 14 Tf 54 720 Td (YUEKE CROSS CLIENT ${safeLabel}) Tj ET\n`
  const objects = [
    null,
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [4 0 R] /Count 1 >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>',
    `<< /Length ${Buffer.byteLength(stream, 'ascii')} >>\nstream\n${stream}endstream`,
  ]
  let body = '%PDF-1.4\n%YUEKE E2E CROSS CLIENT DOCUMENT\n'
  const offsets = [0]
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = Buffer.byteLength(body, 'ascii')
    body += `${id} 0 obj\n${objects[id]}\nendobj\n`
  }
  const xrefOffset = Buffer.byteLength(body, 'ascii')
  body += `xref\n0 ${objects.length}\n0000000000 65535 f \n`
  for (let id = 1; id < objects.length; id += 1) body += `${String(offsets[id]).padStart(10, '0')} 00000 n \n`
  body += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  return Buffer.from(body, 'ascii')
}

async function loginTeacherMini(page) {
  await page.goto(`${MINI_BASE}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(config.mentor.username)
  await fields.nth(1).fill(config.mentor.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.mentor.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 15_000 })
}

async function setTeacherBatch(page, fixture) {
  await page.evaluate(({ key, batch }) => {
    window.localStorage.setItem(key, JSON.stringify(batch))
  }, {
    key: TEACHER_BATCH_KEY,
    batch: { id: String(fixture.batchId), name: fixture.batchName || '', status: 'RUNNING' }
  })
}

async function expectRenderedPdfCanvas(page) {
  const adapter = page.locator('[data-preview-adapter="pdf"]')
  await expect(adapter, 'teacher PC must select the PDF adapter').toBeVisible({ timeout: 30_000 })
  const canvas = adapter.locator('canvas').first()
  await expect(canvas, 'teacher PC must render the thesis into a real PDF.js canvas').toBeVisible({ timeout: 30_000 })
  await expect.poll(async () => canvas.evaluate((node) => ({
    width: Number(node.width || 0), height: Number(node.height || 0),
    cssWidth: Math.round(node.getBoundingClientRect().width), cssHeight: Math.round(node.getBoundingClientRect().height)
  })), { message: 'PDF canvas must have real bitmap and visible dimensions' }).toMatchObject({
    width: expect.any(Number), height: expect.any(Number), cssWidth: expect.any(Number), cssHeight: expect.any(Number)
  })
  const size = await canvas.evaluate((node) => ({
    width: Number(node.width || 0), height: Number(node.height || 0),
    cssWidth: node.getBoundingClientRect().width, cssHeight: node.getBoundingClientRect().height
  }))
  expect(size.width).toBeGreaterThan(100)
  expect(size.height).toBeGreaterThan(100)
  expect(size.cssWidth).toBeGreaterThan(100)
  expect(size.cssHeight).toBeGreaterThan(100)
}

async function ensurePendingFinal(page, fixture) {
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  await student.signTaskbookIfNeeded()

  const proposalStep = student.step('开题')
  const proposalText = await proposalStep.innerText()
  const proposalApproved = /已通过|书面开题通过/.test(proposalText)
  const proposalPending = /待.*审|已提交/.test(proposalText)
  if (!proposalApproved && !proposalPending) {
    await student.submitProposal({ suffix: `${fixture.runId}-cross-client`, fileName: `cross-client-proposal-${fixture.runId}.pdf` })
  }
  if (!proposalApproved) {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await staff.openProposals('PENDING_REVIEW')
    await staff.selectStudent()
    await staff.approve()
  }

  execFileSync('python', ['scripts/e2e_seed_graduation_final_prerequisite.py', fixture.gdStudentId], {
    cwd: BACKEND_DIR, env: { ...process.env, PYTHONPATH: BACKEND_DIR }, encoding: 'utf8'
  })

  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  await student.open()
  const finalStep = page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: /成果/ }) }).first()
  await expect(finalStep).toBeVisible()
  const finalText = await finalStep.innerText()
  if (/待.*审|已提交/.test(finalText)) return

  let fileInput = finalStep.locator('input[type=file]')
  if (!(await fileInput.count())) {
    const openFinal = finalStep.getByRole('button').filter({ hasText: /提交|修改|重交|完善|成果/ }).first()
    await expect(openFinal).toBeVisible()
    await openFinal.click()
    fileInput = finalStep.locator('input[type=file]')
  }
  await expect(fileInput).toHaveCount(1)

  const uploadPromise = page.waitForResponse((response) => {
    const target = new URL(response.url())
    return response.request().method() === 'POST' && target.pathname.endsWith('/files')
  })
  await fileInput.setInputFiles({
    name: `cross-client-thesis-${fixture.runId}.pdf`, mimeType: 'application/pdf', buffer: buildPreviewablePdf(fixture.runId)
  })
  const uploaded = await expectBusinessSuccess(await uploadPromise, '学生 PC 上传毕业论文')
  expect(uploaded?.fileId).toBeTruthy()

  const submitButton = finalStep.getByRole('button', { name: /提交论文成果/ })
  await expect(submitButton).toBeEnabled()
  const [submitResponse] = await Promise.all([
    page.waitForResponse((response) => response.request().method() === 'POST' && response.url().includes('/portal/graduation/final/submit')),
    submitButton.click()
  ])
  const submitted = await expectBusinessSuccess(submitResponse, '学生 PC 提交毕业论文')
  expect(submitted?.status).toBe('PENDING_REVIEW')
  await expect(finalStep).toContainText(/待.*审|已提交/)
}

test.describe.serial('V6 · one real thesis across student PC, teacher PC and teacher miniapp', () => {
  let fixture

  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  test('same canonical FileVersion is visible and previewable on all required surfaces', async ({ page }, testInfo) => {
    test.setTimeout(8 * 60_000)
    await ensurePendingFinal(page, fixture)

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
    await dismissGuide(page)

    const workspace = page.locator('.gd-review-workspace')
    await expect(workspace).toBeVisible()
    await expect(workspace.locator('.gd-review-workspace__queue')).toContainText(fixture.topicTitle)
    await expect.poll(() => new URL(page.url()).searchParams.get('sel'), { message: 'teacher PC must expose the exact selected final record in URL' }).toMatch(/^\d+$/)
    const recordId = String(new URL(page.url()).searchParams.get('sel'))
    const command = page.getByTestId('review-command-contract')
    await expect(command).toContainText('文件版本')
    await expect(command).toContainText('可以批阅')
    const materialVersion = (await command.locator('div').nth(0).locator('b').innerText()).trim()
    const fileVersionId = (await command.locator('div').nth(1).locator('b').innerText()).trim()
    expect(materialVersion).toMatch(/^\d+$/)
    expect(fileVersionId).toMatch(/^\d+$/)
    await expectRenderedPdfCanvas(page)

    const pcShot = testInfo.outputPath('cross-client-thesis-teacher-pc.png')
    await page.screenshot({ path: pcShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-teacher-pc', { path: pcShot, contentType: 'image/png' })

    await page.setViewportSize({ width: 390, height: 844 })
    await loginTeacherMini(page)
    await setTeacherBatch(page, fixture)
    const taskQuery = new URLSearchParams({
      tab: 'review', kind: 'final', batchId: String(fixture.batchId),
      gdStudentId: String(fixture.gdStudentId), recordId, materialVersion, fileVersionId
    })
    await page.goto(`${MINI_BASE}/#/pages/teacher/graduation-guide/index?${taskQuery}`)

    await expect(page.getByText('成果待批阅', { exact: true })).toBeVisible({ timeout: 20_000 })
    const studentCard = page.locator('.gg').filter({ hasText: fixture.topicTitle }).first()
    await expect(studentCard, 'teacher miniapp must receive the exact pending thesis').toBeVisible({ timeout: 20_000 })
    await studentCard.getByRole('button', { name: '去批阅成果' }).click()

    const review = page.locator('.rv__content')
    await expect(review).toBeVisible({ timeout: 20_000 })
    await expect(review).toContainText(fixture.topicTitle)
    const versionRow = page.locator('.rv__att').filter({ hasText: `FileVersion ${fileVersionId}` }).first()
    await expect(versionRow, 'teacher miniapp must show the same canonical FileVersion as teacher PC').toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.rv__foot').getByRole('button', { name: '通过' })).toBeEnabled()
    await expect(page.locator('.rv__foot').getByRole('button', { name: '退回' })).toBeEnabled()

    const ticketPromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
      && /\/api\/v1\/mobile\/graduation\/material-center\/files\/[^/]+\/ticket$/.test(new URL(response.url()).pathname)
    )
    const previewPromise = page.waitForResponse((response) =>
      response.request().method() === 'GET'
      && /\/api\/v1\/mobile\/graduation\/material-center\/files\/[^/]+\/preview$/.test(new URL(response.url()).pathname)
      && new URL(response.url()).searchParams.has('ticket')
    )
    await versionRow.click()
    const ticketData = await expectBusinessSuccess(await ticketPromise, '教师小程序签发论文预览票据')
    expect(ticketData?.ticket || ticketData?.url || ticketData?.previewUrl).toBeTruthy()
    const previewResponse = await previewPromise
    expect(previewResponse.ok(), `teacher miniapp PDF preview HTTP ${previewResponse.status()}`).toBeTruthy()
    const previewBytes = await previewResponse.body()
    expect(previewBytes.subarray(0, 5).toString('ascii')).toBe('%PDF-')

    const confirmCurrent = page.getByRole('button', { name: '确认当前版本' })
    if (await confirmCurrent.isVisible().catch(() => false)) {
      const revalidatePromise = page.waitForResponse((response) =>
        response.request().method() === 'GET'
        && /\/api\/v1\/mobile\/teacher\/graduation\/final\/[^/]+$/.test(new URL(response.url()).pathname)
      )
      await confirmCurrent.click()
      const fresh = await expectBusinessSuccess(await revalidatePromise, '教师小程序预览返回后重验论文版本')
      expect(String(fresh?.materialVersion || '')).toBe(materialVersion)
      expect(String(fresh?.fileVersionId || '')).toBe(fileVersionId)
      await expect(page.locator('.rv__foot').getByRole('button', { name: '通过' })).toBeEnabled()
      await expect(page.locator('.rv__foot').getByRole('button', { name: '退回' })).toBeEnabled()
    }
    await expect(page.locator('body')).not.toContainText(/版本已变化|旧版审核已锁定|批次与当前选择不一致|指定的毕业设计待办不在当前批次/)

    const miniShot = testInfo.outputPath('cross-client-thesis-teacher-miniapp.png')
    await page.screenshot({ path: miniShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-teacher-miniapp', { path: miniShot, contentType: 'image/png' })
  })
})
