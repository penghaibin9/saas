import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { expect } from './observability.mjs'
import { config } from './config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const BACKEND_DIR = fileURLToPath(new URL('../../backend/', import.meta.url))
const PROPOSAL_APPROVED = /已通过|书面开题通过/
const PROPOSAL_PENDING = /待.*审|已提交|审核中/
const FINAL_PENDING = /待.*审|已提交|审核中/

function serializePdfObjects(objects) {
  let body = '%PDF-1.4\n%YUEKE E2E GRADUATION SCENARIO\n'
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

export function buildGraduationScenarioPdf(label, pages = 20) {
  const pageCount = Math.max(1, Number(pages) || 1)
  const safeLabel = String(label || 'scenario').replace(/[()\\]/g, '')
  const objects = [null]
  const pageIds = []
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>'
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'

  for (let pageNo = 1; pageNo <= pageCount; pageNo += 1) {
    const pageId = 4 + (pageNo - 1) * 2
    const contentId = pageId + 1
    pageIds.push(pageId)
    const line = `YUEKE GRADUATION ${safeLabel} PAGE ${pageNo}/${pageCount}`
    const stream = `BT /F1 14 Tf 54 720 Td (${line}) Tj ET\n`
    objects[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`
    objects[contentId] = `<< /Length ${Buffer.byteLength(stream, 'ascii')} >>\nstream\n${stream}endstream`
  }
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pageCount} >>`
  return serializePdfObjects(objects)
}

export async function dismissGraduationGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      else await page.keyboard.press('Escape').catch(() => {})
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

export async function expectGraduationBusinessSuccess(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  if (body && Object.prototype.hasOwnProperty.call(body, 'code')) {
    expect(body.code, `${action} business error: ${text.slice(0, 800)}`).toBe(0)
  }
  return body?.data ?? body
}

async function openStudentWorkbench(page) {
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  return student
}

export async function ensureProposalApproved(page, fixture, { suffix = 'scenario' } = {}) {
  let student = await openStudentWorkbench(page)
  await student.signTaskbookIfNeeded()
  let proposalStep = student.step('开题')
  let state = await proposalStep.innerText()

  if (!PROPOSAL_APPROVED.test(state) && !PROPOSAL_PENDING.test(state)) {
    await student.submitProposal({
      suffix: `${fixture.runId}-${suffix}`,
      fileName: `proposal-${fixture.runId}-${suffix}.pdf`,
      pages: 1
    })
    proposalStep = student.step('开题')
    state = await proposalStep.innerText()
  }

  if (!PROPOSAL_APPROVED.test(state)) {
    expect(state, 'proposal must be pending before mentor approval').toMatch(PROPOSAL_PENDING)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await staff.openProposals('PENDING_REVIEW')
    await staff.selectStudent()
    await staff.approve()

    student = await openStudentWorkbench(page)
    await expect.poll(async () => student.step('开题').innerText(), {
      message: 'proposal must read back as approved after mentor review',
      timeout: 30_000
    }).toMatch(PROPOSAL_APPROVED)
  }

  return student
}

export async function ensureFinalPending(page, fixture, {
  suffix = 'scenario',
  documentPages = 20
} = {}) {
  await ensureProposalApproved(page, fixture, { suffix })

  execFileSync(
    'python',
    ['scripts/e2e_seed_graduation_final_prerequisite.py', fixture.gdStudentId],
    {
      cwd: BACKEND_DIR,
      env: { ...process.env, PYTHONPATH: BACKEND_DIR },
      encoding: 'utf8'
    }
  )

  const student = await openStudentWorkbench(page)
  const finalStep = page.locator('.gd-step').filter({
    has: page.getByRole('heading', { name: /成果/ })
  }).first()
  await expect(finalStep).toBeVisible()
  const current = await finalStep.innerText()
  if (FINAL_PENDING.test(current)) return { reused: true, state: current }
  if (/已通过/.test(current)) {
    throw new Error('final scenario is already approved; use a fresh scenario namespace instead of mutating history')
  }

  let fileInput = finalStep.locator('input[type=file]')
  if (!(await fileInput.count())) {
    const open = finalStep.getByRole('button').filter({ hasText: /提交|修改|重交|完善|成果/ }).first()
    await expect(open, 'student final form must be reachable').toBeVisible()
    await open.click()
    fileInput = finalStep.locator('input[type=file]')
  }
  await expect(fileInput).toHaveCount(1)

  const uploadPromise = page.waitForResponse((response) => {
    const target = new URL(response.url())
    return response.request().method() === 'POST' && target.pathname.endsWith('/files')
  })
  await fileInput.setInputFiles({
    name: `thesis-${fixture.runId}-${suffix}.pdf`,
    mimeType: 'application/pdf',
    buffer: buildGraduationScenarioPdf(`${fixture.runId}-${suffix}`, documentPages)
  })
  const uploaded = await expectGraduationBusinessSuccess(await uploadPromise, '学生 PC 上传毕业论文')
  expect(uploaded?.fileId, 'uploaded thesis must return fileId').toBeTruthy()

  const submit = finalStep.getByRole('button', { name: /提交论文成果/ })
  await expect(submit).toBeEnabled()
  const [response] = await Promise.all([
    page.waitForResponse((candidate) =>
      candidate.request().method() === 'POST'
      && candidate.url().includes('/portal/graduation/final/submit')
    ),
    submit.click()
  ])
  const submitted = await expectGraduationBusinessSuccess(response, '学生 PC 提交毕业论文')
  expect(submitted?.status).toBe('PENDING_REVIEW')
  await expect(finalStep).toContainText(FINAL_PENDING)
  return { reused: false, submitted }
}

export async function expectRenderedPdfCanvas(page) {
  const adapter = page.locator('[data-preview-adapter="pdf"]')
  await expect(adapter, 'teacher PC must select the PDF adapter').toBeVisible({ timeout: 30_000 })
  const canvas = adapter.locator('canvas').first()
  await expect(canvas, 'teacher PC must render the thesis into a real PDF.js canvas').toBeVisible({ timeout: 30_000 })
  await expect.poll(async () => canvas.evaluate((node) => ({
    width: Number(node.width || 0),
    height: Number(node.height || 0),
    cssWidth: Math.round(node.getBoundingClientRect().width),
    cssHeight: Math.round(node.getBoundingClientRect().height)
  })), { message: 'PDF canvas must have real bitmap and visible dimensions' }).toMatchObject({
    width: expect.any(Number),
    height: expect.any(Number),
    cssWidth: expect.any(Number),
    cssHeight: expect.any(Number)
  })
  const size = await canvas.evaluate((node) => ({
    width: Number(node.width || 0),
    height: Number(node.height || 0),
    cssWidth: node.getBoundingClientRect().width,
    cssHeight: node.getBoundingClientRect().height
  }))
  expect(size.width).toBeGreaterThan(100)
  expect(size.height).toBeGreaterThan(100)
  expect(size.cssWidth).toBeGreaterThan(100)
  expect(size.cssHeight).toBeGreaterThan(100)
}
