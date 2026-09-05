import { expect } from './observability.mjs'
import { config } from './config.mjs'
import { graduationRoles } from './graduation-role-accounts.mjs'
import { items, loginApi } from './api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const PROPOSAL_APPROVED = 'APPROVED'
const PROPOSAL_PENDING = 'PENDING_REVIEW'
const FINAL_PENDING = 'PENDING_REVIEW'
const FINAL_APPROVED = 'APPROVED'
const MIDTERM_APPROVED = new Set(['CHECKED_PASS', 'RECTIFIED_PASS'])
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
  const pageCount = Math.max(1, Math.floor(Number(pages) || 1))
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
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (!(await mask.isVisible().catch(() => false))) continue
    const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
    if (await skip.isVisible().catch(() => false)) await skip.click()
    else await page.keyboard.press('Escape')
    await expect(mask, 'the guide must not obscure the business operation or screenshot').toBeHidden()
  }
}

export async function expectGraduationBusinessSuccess(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  expect(body, `${action} must return a JSON business envelope`).not.toBeNull()
  expect(body.code, `${action} business error: ${text.slice(0, 800)}`).toBe(0)
  return body.data
}

async function openStudentWorkbench(page, fixture) {
  const studentAccount = fixture?.studentAccount || config.student
  await new StudentLoginPage(page, config.studentBaseUrl).login(studentAccount)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  await expect(page.locator('.gd-summary'), 'student account must resolve the intended graduation record').toContainText(fixture.topicTitle)
  return student
}

/** Read canonical enums, never explanatory copy such as “等待审核”. */
export async function ensureProposalApproved(page, fixture, { suffix = 'scenario' } = {}) {
  const studentApi = await loginApi(fixture?.studentAccount || config.student)
  const read = () => studentApi.get('/portal/graduation/proposal')
  let student = await openStudentWorkbench(page, fixture)
  await student.signTaskbookIfNeeded()
  let snapshot = await read()
  let state = String(snapshot?.latest?.status || '')

  if (state !== PROPOSAL_APPROVED && state !== PROPOSAL_PENDING) {
    expect(snapshot?.canSubmit, `proposal cannot be submitted: ${snapshot?.reason || state}`).toBe(true)
    await student.submitProposal({
      suffix: `${fixture.runId}-${suffix}`,
      fileName: `proposal-${fixture.runId}-${suffix}.pdf`,
      pages: 1
    })
    await expect.poll(async () => String((await read())?.latest?.status || ''), {
      message: 'student submission must persist as PENDING_REVIEW', timeout: 30_000
    }).toBe(PROPOSAL_PENDING)
    snapshot = await read()
    state = String(snapshot?.latest?.status || '')
  }

  if (state !== PROPOSAL_APPROVED) {
    expect(state).toBe(PROPOSAL_PENDING)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
    await staff.openProposals('PENDING_REVIEW')
    const row = page.locator('.pr-row').filter({ hasText: fixture.topicTitle })
    await expect(row, 'the mentor must see the exact submitted student, not the first queue item').toHaveCount(1)
    await row.click()
    await expect(page.locator('.prc')).toContainText(fixture.topicTitle)
    await expectRenderedPdfCanvas(page)
    await staff.approve()
    await expect.poll(async () => String((await read())?.latest?.status || ''), {
      message: 'mentor approval must read back to the submitting student', timeout: 30_000
    }).toBe(PROPOSAL_APPROVED)
    student = await openStudentWorkbench(page, fixture)
  }
  return student
}

/** Complete the existing teacher-PC midterm form; do not seed an approved DB row. */
export async function ensureMidtermApproved(page, fixture) {
  const mentorApi = await loginApi(config.mentor)
  const params = { batchId: fixture.batchId }
  const read = () => mentorApi.get(`/graduation/gd-midterms/${fixture.gdStudentId}`, params)
  const current = await read()
  if (MIDTERM_APPROVED.has(String(current?.status || ''))) return current
  if (['RECTIFYING', 'RECTIFY_SUBMITTED', 'CHECKED_FAIL'].includes(String(current?.status || ''))) {
    throw new Error(`Midterm ${current.status} requires its student rectification/review journey; refusing to overwrite it.`)
  }
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
  const returnTo = `/admin/graduation/process?panel=midterm&studentId=${fixture.gdStudentId}&batchId=${fixture.batchId}`
  const query = new URLSearchParams({ ...params, studentId: fixture.gdStudentId, panel: 'midterm', returnTo })
  await page.goto(`${config.staffBaseUrl}/admin/graduation/process/${fixture.gdStudentId}/midterm?${query}`)
  await dismissGraduationGuide(page)
  await expect(page.getByRole('heading', { name: '发起中期检查', exact: true })).toBeVisible()
  await page.getByLabel('检查意见', { exact: false }).fill('已核对开题及当前研究进展，中期检查通过，继续完成论文初稿。')
  const responsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
    && new URL(response.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/check`)
  )
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expectGraduationBusinessSuccess(await responsePromise, '指导教师 PC 完成中期检查')
  await expect.poll(async () => String((await read())?.status || ''), {
    message: 'midterm completion must read back from the server', timeout: 30_000
  }).toBe('CHECKED_PASS')
  return read()
}

export async function ensureFinalPending(page, fixture, {
  suffix = 'scenario', documentPages = 20
} = {}) {
  await ensureProposalApproved(page, fixture, { suffix })
  await ensureMidtermApproved(page, fixture)
  const studentApi = await loginApi(fixture?.studentAccount || config.student)
  const read = () => studentApi.get('/portal/graduation/final')
  await openStudentWorkbench(page, fixture)
  const finalStep = page.locator('[data-step-key="final"]')
  await expect(finalStep).toBeVisible()
  const snapshot = await read()
  const pending = (snapshot?.items || []).find((row) => row.status === FINAL_PENDING)
  if (pending) return { reused: true, submitted: pending, state: FINAL_PENDING }
  const latest = snapshot?.items?.[0]
  if (latest?.status === FINAL_APPROVED) return { reused: true, state: FINAL_APPROVED, approved: true }
  expect(Boolean(snapshot?.canSubmitDraft || snapshot?.canSubmitFinal), snapshot?.hint || 'final submission must be allowed').toBe(true)

  let fileInput = finalStep.locator('input[type=file]')
  if (!(await fileInput.count())) {
    const open = finalStep.getByRole('button').filter({ hasText: /提交|修改|重交|完善|成果/ }).first()
    await expect(open, 'student final form must be reachable').toBeVisible()
    await open.click()
    fileInput = finalStep.locator('input[type=file]')
  }
  await expect(fileInput).toHaveCount(1)
  const uploadPromise = page.waitForResponse((response) =>
    response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/files')
  )
  await fileInput.setInputFiles({
    name: `thesis-${fixture.runId}-${suffix}.pdf`, mimeType: 'application/pdf',
    buffer: buildGraduationScenarioPdf(`${fixture.runId}-${suffix}`, documentPages)
  })
  const uploaded = await expectGraduationBusinessSuccess(await uploadPromise, '学生 PC 上传毕业论文')
  expect(uploaded?.fileId, 'uploaded thesis must return fileId').toBeTruthy()
  const submit = finalStep.getByRole('button', { name: /提交论文成果/ })
  await expect(submit).toBeEnabled()
  const [response] = await Promise.all([
    page.waitForResponse((candidate) => candidate.request().method() === 'POST'
      && new URL(candidate.url()).pathname.endsWith('/portal/graduation/final/submit')),
    submit.click()
  ])
  const submitted = await expectGraduationBusinessSuccess(response, '学生 PC 提交毕业论文')
  expect(submitted?.status).toBe(FINAL_PENDING)
  await expect.poll(async () => (await read())?.items?.some((row) =>
    String(row.id) === String(submitted.id) && row.status === FINAL_PENDING
  ), { message: 'submitted final must persist for the same student', timeout: 30_000 }).toBe(true)
  return { reused: false, submitted }
}

async function readFinalRecord(adminApi, fixture) {
  const rows = items(await adminApi.get('/graduation/finals', {
    batchId: fixture.batchId, keyword: fixture.studentNo, page: 1, pageSize: 200
  }))
  return rows.find((row) => String(row.gdStudentId || row.projectId || '') === String(fixture.gdStudentId)) || null
}

/** Isolated defense setup is not counted as the four-client acceptance journey. */
export async function ensureFinalApproved(page, adminApi, fixture, {
  suffix = 'defense-prerequisite', documentPages = 20, timeoutMs = 30_000
} = {}) {
  await ensureFinalPending(page, fixture, { suffix, documentPages })
  let row = await readFinalRecord(adminApi, fixture)
  if (!row) throw new Error(`Final record did not read back for graduation student ${fixture.gdStudentId}.`)
  if (row.status !== FINAL_APPROVED) {
    const mentorApi = await loginApi(config.mentor)
    const detail = await mentorApi.get(`/graduation/finals/${row.id}`, { batchId: fixture.batchId })
    if (!detail?.fileVersionId || detail?.materialVersion == null) {
      throw new Error(`Final record ${row.id} is missing canonical version evidence.`)
    }
    await mentorApi.post(`/graduation/finals/${row.id}/review`, {
      action: 'APPROVE', comment: 'Playwright isolated defense prerequisite approval',
      expectedVersion: detail.materialVersion, fileVersionId: detail.fileVersionId
    }, { batchId: fixture.batchId })
  }
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    row = await readFinalRecord(adminApi, fixture)
    const student = graduationStudentEntity(await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`))
    if (row?.status === FINAL_APPROVED && DEFENSE_ELIGIBLE_STAGES.has(String(student?.stage || ''))) return { final: row, student }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`Final approval did not read back with a defense-eligible stage for student ${fixture.gdStudentId}.`)
}

export async function expectRenderedPdfCanvas(page) {
  const adapter = page.locator('[data-preview-adapter="pdf"]')
  await expect(adapter, 'teacher PC must select the PDF adapter').toBeVisible({ timeout: 30_000 })
  const canvas = adapter.locator('canvas').first()
  await expect(canvas, 'teacher PC must render the thesis into a real PDF.js canvas').toBeVisible({ timeout: 30_000 })
  await expect.poll(async () => canvas.evaluate((node) => {
    const rect = node.getBoundingClientRect()
    return node.width > 100 && node.height > 100 && rect.width > 100 && rect.height > 100
  }), { message: 'PDF canvas must have real bitmap and visible dimensions', timeout: 30_000 }).toBe(true)
}

function graduationStudentEntity(data) { return data?.student || data || null }
function dateTimeAfterDays(days) {
  return new Date(Date.now() + Number(days || 0) * 86400000).toISOString().slice(0, 16).replace('T', ' ')
}

async function ensureDefenseEligibleStudent(page, adminApi, fixture) {
  let student = graduationStudentEntity(await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`))
  if (!DEFENSE_ELIGIBLE_STAGES.has(String(student?.stage || '').toUpperCase())) {
    await ensureFinalApproved(page, adminApi, fixture)
    student = graduationStudentEntity(await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`))
  }
  const stage = String(student?.stage || '').toUpperCase()
  if (!DEFENSE_ELIGIBLE_STAGES.has(stage)) throw new Error(`Graduation student ${fixture.gdStudentId} did not read back in a defense-eligible stage; got ${stage || 'EMPTY'}.`)
  return student
}

async function ensureScenarioMentor(adminApi, account, {
  teacherName, title = '副教授', researchDirection = '毕业设计评阅与答辩'
}) {
  const read = async () => items(await adminApi.get('/graduation/gd-mentors', {
    keyword: account.username, page: 1, pageSize: 200
  })).find((row) => String(row.teacherNo || '') === String(account.username))
  let mentor = await read()
  if (!mentor) mentor = await adminApi.post('/graduation/gd-mentors', {
    teacherNo: account.username, teacherName, mentorType: 'INTERNAL', title,
    researchDirection, maxCapacity: 30, submitReview: true,
    remark: 'Playwright shared graduation role fixture'
  })
  const status = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(status)) {
    try {
      await adminApi.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE', comment: 'Playwright shared graduation role fixture approved'
      })
    } catch (error) {
      if (!/已审核|无需审核|状态|APPROVED|QUALIFIED/i.test(String(error?.message || ''))) throw error
    }
    mentor = await read() || mentor
  }
  const latestStatus = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(latestStatus)) throw new Error(`Graduation mentor ${account.username} did not read back as approved; got ${latestStatus || 'EMPTY'}.`)
  return mentor
}

export async function ensureDefenseScoringContext(page, adminApi, fixture) {
  const expert = await ensureScenarioMentor(adminApi, graduationRoles.defenseExpert, { teacherName: 'E2E答辩专家A', title: '副教授' })
  const chair = await ensureScenarioMentor(adminApi, graduationRoles.defenseChair, { teacherName: 'E2E答辩专家B', title: '教授' })
  const secretary = await ensureScenarioMentor(adminApi, graduationRoles.defenseSecretary, { teacherName: 'E2E学院秘书', title: '讲师' })
  const groupName = `Playwright 评委工作区 ${fixture.runId}`
  const readGroup = async () => items(await adminApi.get('/graduation/defense-groups', {
    batchId: fixture.batchId, keyword: groupName, page: 1, pageSize: 200
  })).find((row) => String(row.groupName || '') === groupName)
  let group = await readGroup()
  if (!group) group = await adminApi.post('/graduation/defense-groups', {
    groupName, batchId: Number(fixture.batchId), defenseDate: dateTimeAfterDays(14), location: '实训楼 A302',
    chair: chair.teacherName || 'E2E答辩专家B', chairMentorId: Number(chair.id),
    members: [expert.teacherName || 'E2E答辩专家A'], memberMentorIds: [Number(expert.id)],
    secretary: secretary.teacherName || 'E2E学院秘书', secretaryMentorId: Number(secretary.id)
  }, { batchId: fixture.batchId })
  let student = await ensureDefenseEligibleStudent(page, adminApi, fixture)
  if (String(student?.defenseGroupId || '') !== String(group.id)) {
    await adminApi.post(`/graduation/defense-groups/${group.id}/assign`, { studentIds: [String(fixture.gdStudentId)] }, { batchId: fixture.batchId })
    student = graduationStudentEntity(await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`))
  }
  if (String(student?.defenseGroupId || '') !== String(group.id)) throw new Error(`Defense group ${group.id} did not read back on student ${fixture.gdStudentId}.`)
  group = await adminApi.get(`/graduation/defense-groups/${group.id}`, { batchId: fixture.batchId })
  if (!group.published) {
    await adminApi.post(`/graduation/defense-groups/${group.id}/publish`, {}, { batchId: fixture.batchId })
    group = await adminApi.get(`/graduation/defense-groups/${group.id}`, { batchId: fixture.batchId })
  }
  if (!group.published) throw new Error(`Defense group ${group.id} did not read back as published.`)
  const seats = group.memberDetails || group.members || []
  const expertIsSeated = seats.some((seat) => {
    if (typeof seat === 'string') return seat === (expert.teacherName || 'E2E答辩专家A')
    return String(seat.mentorId || '') === String(expert.id) || String(seat.name || seat.teacherName || '') === String(expert.teacherName || 'E2E答辩专家A')
  })
  if (!expertIsSeated) throw new Error(`Defense expert ${graduationRoles.defenseExpert.username} is not on group ${group.id}.`)
  return { ...fixture, defenseGroupId: String(group.id), defenseExpertMentorId: String(expert.id), defenseExpertName: expert.teacherName || 'E2E答辩专家A' }
}

export async function ensureArchiveProjection(adminApi, fixture, { timeoutMs = 30_000 } = {}) {
  const query = { batchId: fixture.batchId, keyword: fixture.studentNo, page: 1, pageSize: 200 }
  const read = async () => items(await adminApi.get('/graduation/gd-archives', query)).find((row) =>
    String(row.gdStudentId || '') === String(fixture.gdStudentId) || String(row.studentNo || '') === String(fixture.studentNo)
  )
  let archive = await read()
  if (!archive) {
    try {
      await adminApi.post(`/graduation/gd-archives/${fixture.gdStudentId}/generate`, {}, { batchId: fixture.batchId })
    } catch (error) {
      if (!/已生成|重复|存在|DATA_CONFLICT/i.test(String(error?.message || ''))) throw error
    }
  }
  const deadline = Date.now() + timeoutMs
  while (!archive && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 500))
    archive = await read()
  }
  if (!archive) throw new Error(`Archive projection did not read back for gdStudentId=${fixture.gdStudentId}, batchId=${fixture.batchId}.`)
  if (archive.batchId != null && String(archive.batchId) !== String(fixture.batchId)) throw new Error(`Archive projection crossed batch boundary: expected ${fixture.batchId}, got ${archive.batchId}.`)
  return archive
}
