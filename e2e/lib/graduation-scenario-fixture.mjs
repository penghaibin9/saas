import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { expect } from './observability.mjs'
import { config } from './config.mjs'
import { graduationRoles } from './graduation-role-accounts.mjs'
import { items } from './api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const BACKEND_DIR = fileURLToPath(new URL('../../backend/', import.meta.url))
const PROPOSAL_APPROVED = /已通过|书面开题通过/
const PROPOSAL_PENDING = /待.*审|已提交|审核中/
const FINAL_PENDING = /待.*审|已提交|审核中/
const DEFENSE_ELIGIBLE_STAGES = new Set(['FINAL_CHECK', 'DEFENSE', 'COMPLETED'])

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

function graduationStudentEntity(data) {
  return data?.student || data || null
}

function dateTimeAfterDays(days) {
  const date = new Date(Date.now() + Number(days || 0) * 24 * 60 * 60 * 1000)
  return date.toISOString().slice(0, 16).replace('T', ' ')
}

async function ensureDefenseEligibleStudent(adminApi, fixture) {
  const read = async () => graduationStudentEntity(
    await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`)
  )
  let student = await read()
  if (!DEFENSE_ELIGIBLE_STAGES.has(String(student?.stage || '').toUpperCase())) {
    execFileSync(
      'python',
      ['scripts/e2e_seed_graduation_final_prerequisite.py', fixture.gdStudentId],
      {
        cwd: BACKEND_DIR,
        env: { ...process.env, PYTHONPATH: BACKEND_DIR },
        encoding: 'utf8'
      }
    )
    student = await read()
  }
  const stage = String(student?.stage || '').toUpperCase()
  if (!DEFENSE_ELIGIBLE_STAGES.has(stage)) {
    throw new Error(`Graduation student ${fixture.gdStudentId} did not read back in a defense-eligible stage; got ${stage || 'EMPTY'}.`)
  }
  return student
}

async function ensureScenarioMentor(adminApi, account, {
  teacherName,
  title = '副教授',
  researchDirection = '毕业设计评阅与答辩'
}) {
  const read = async () => items(await adminApi.get('/graduation/gd-mentors', {
    keyword: account.username,
    page: 1,
    pageSize: 200
  })).find((row) => String(row.teacherNo || '') === String(account.username))

  let mentor = await read()
  if (!mentor) {
    mentor = await adminApi.post('/graduation/gd-mentors', {
      teacherNo: account.username,
      teacherName,
      mentorType: 'INTERNAL',
      title,
      researchDirection,
      maxCapacity: 30,
      submitReview: true,
      remark: 'Playwright shared graduation role fixture'
    })
  }

  const status = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(status)) {
    try {
      await adminApi.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE',
        comment: 'Playwright shared graduation role fixture approved'
      })
    } catch (error) {
      if (!/已审核|无需审核|状态|APPROVED|QUALIFIED/i.test(String(error?.message || ''))) throw error
    }
    mentor = await read() || mentor
  }

  const latestStatus = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(latestStatus)) {
    throw new Error(`Graduation mentor ${account.username} did not read back as approved; got ${latestStatus || 'EMPTY'}.`)
  }
  return mentor
}

/**
 * Build one stable defense context for the dedicated judge account. The helper
 * owns the complete relation graph and advances only the isolated E2E process
 * prerequisite when server truth says the student is not defense-eligible.
 */
export async function ensureDefenseScoringContext(adminApi, fixture) {
  const expert = await ensureScenarioMentor(adminApi, graduationRoles.defenseExpert, {
    teacherName: 'E2E答辩专家A',
    title: '副教授'
  })
  const chair = await ensureScenarioMentor(adminApi, graduationRoles.defenseChair, {
    teacherName: 'E2E答辩专家B',
    title: '教授'
  })
  const secretary = await ensureScenarioMentor(adminApi, graduationRoles.defenseSecretary, {
    teacherName: 'E2E学院秘书',
    title: '讲师'
  })

  const groupName = `Playwright 评委工作区 ${fixture.runId}`
  const readGroup = async () => items(await adminApi.get('/graduation/defense-groups', {
    batchId: fixture.batchId,
    keyword: groupName,
    page: 1,
    pageSize: 200
  })).find((row) => String(row.groupName || '') === groupName)

  let group = await readGroup()
  if (!group) {
    group = await adminApi.post('/graduation/defense-groups', {
      groupName,
      batchId: Number(fixture.batchId),
      defenseDate: dateTimeAfterDays(14),
      location: '实训楼 A302',
      chair: chair.teacherName || 'E2E答辩专家B',
      chairMentorId: Number(chair.id),
      members: [expert.teacherName || 'E2E答辩专家A'],
      memberMentorIds: [Number(expert.id)],
      secretary: secretary.teacherName || 'E2E学院秘书',
      secretaryMentorId: Number(secretary.id)
    }, { batchId: fixture.batchId })
  }

  let student = await ensureDefenseEligibleStudent(adminApi, fixture)
  if (String(student?.defenseGroupId || '') !== String(group.id)) {
    await adminApi.post(`/graduation/defense-groups/${group.id}/assign`, {
      studentIds: [String(fixture.gdStudentId)]
    }, { batchId: fixture.batchId })
    student = graduationStudentEntity(await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`))
  }
  if (String(student?.defenseGroupId || '') !== String(group.id)) {
    throw new Error(`Defense group ${group.id} did not read back on student ${fixture.gdStudentId}.`)
  }

  group = await adminApi.get(`/graduation/defense-groups/${group.id}`, { batchId: fixture.batchId })
  if (!group.published) {
    await adminApi.post(`/graduation/defense-groups/${group.id}/publish`, {}, { batchId: fixture.batchId })
    group = await adminApi.get(`/graduation/defense-groups/${group.id}`, { batchId: fixture.batchId })
  }
  if (!group.published) throw new Error(`Defense group ${group.id} did not read back as published.`)

  const seats = group.memberDetails || group.members || []
  const expertIsSeated = seats.some((seat) => {
    if (typeof seat === 'string') return seat === (expert.teacherName || 'E2E答辩专家A')
    return String(seat.mentorId || '') === String(expert.id)
      || String(seat.name || seat.teacherName || '') === String(expert.teacherName || 'E2E答辩专家A')
  })
  if (!expertIsSeated) throw new Error(`Defense expert ${graduationRoles.defenseExpert.username} is not on group ${group.id}.`)

  return {
    ...fixture,
    defenseGroupId: String(group.id),
    defenseExpertMentorId: String(expert.id),
    defenseExpertName: expert.teacherName || 'E2E答辩专家A'
  }
}

/**
 * Archive fixtures are read-before-write and server-readback. The browser must
 * never navigate to the archive queue based only on a successful POST response.
 */
export async function ensureArchiveProjection(adminApi, fixture, { timeoutMs = 30_000 } = {}) {
  const query = {
    batchId: fixture.batchId,
    keyword: fixture.studentNo,
    page: 1,
    pageSize: 200
  }
  const read = async () => items(await adminApi.get('/graduation/gd-archives', query)).find((row) =>
    String(row.gdStudentId || '') === String(fixture.gdStudentId)
      || String(row.studentNo || '') === String(fixture.studentNo)
  )

  let archive = await read()
  if (!archive) {
    try {
      await adminApi.post(`/graduation/gd-archives/${fixture.gdStudentId}/generate`, {}, {
        batchId: fixture.batchId
      })
    } catch (error) {
      if (!/已生成|重复|存在|DATA_CONFLICT/i.test(String(error?.message || ''))) throw error
    }
  }

  const deadline = Date.now() + timeoutMs
  while (!archive && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 500))
    archive = await read()
  }
  if (!archive) {
    throw new Error(`Archive projection did not read back for gdStudentId=${fixture.gdStudentId}, batchId=${fixture.batchId}.`)
  }
  if (archive.batchId != null && String(archive.batchId) !== String(fixture.batchId)) {
    throw new Error(`Archive projection crossed batch boundary: expected ${fixture.batchId}, got ${archive.batchId}.`)
  }
  return archive
}