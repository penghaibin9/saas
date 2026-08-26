import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const actorIp = {
  student: '10.251.0.61',
  mentor: '10.251.0.62',
  admin: '10.251.0.63',
}

async function loginStudent(page) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': actorIp.student })
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
}

async function loginMentor(page) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': actorIp.mentor })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
}

async function loginAdmin(page) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': actorIp.admin })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
}

async function resumeStudent(page, student, marker) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': actorIp.student })
  const refreshPromise = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-refresh') && response.request().method() === 'POST'
  )
  await student.open()
  const refreshResponse = await refreshPromise
  expect(refreshResponse.ok(), `${marker} student browser-refresh HTTP ${refreshResponse.status()}`).toBeTruthy()
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function establishApprovedProposal(page, fixture) {
  await loginStudent(page)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  await student.signTaskbookIfNeeded()
  await student.submitProposal({
    suffix: `${fixture.runId}-final-prereq`,
    fileName: `E2E-AUDIT-20260823-final-prereq-${fixture.runId}.pdf`
  })
  await loginMentor(page)
  const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
  await staff.openProposals('PENDING_REVIEW')
  await staff.selectStudent()
  await staff.approve()
}

async function reachFinalCheckThroughUi(page, fixture) {
  await establishApprovedProposal(page, fixture)

  await loginAdmin(page)
  const detailUrl = new URL(`${config.staffBaseUrl}/admin/graduation/students/${fixture.gdStudentId}`)
  detailUrl.searchParams.set('batchId', fixture.batchId)
  detailUrl.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(detailUrl.toString())
  await dismissGuide(page)
  const stage = page.locator('.gsd-summary__item').filter({ hasText: '当前节点' }).first()
  await expect(stage).toContainText('指导中')
  await page.getByRole('button', { name: '推进节点', exact: true }).click()
  const [advanceResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-students/${fixture.gdStudentId}/stage`)),
    page.getByRole('button', { name: '推进', exact: true }).click()
  ])
  expect(advanceResponse.ok()).toBeTruthy()
  expect((await advanceResponse.json()).code).toBe(0)
  await expect(stage).toContainText('中期检查')

  await loginMentor(page)
  const processUrl = new URL(`${config.staffBaseUrl}/admin/graduation/process`)
  processUrl.searchParams.set('batchId', fixture.batchId)
  processUrl.searchParams.set('studentId', fixture.gdStudentId)
  processUrl.searchParams.set('panel', 'midterm')
  processUrl.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(processUrl.toString())
  await dismissGuide(page)
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
  await page.getByRole('button', { name: '发起中期检查', exact: true }).click()
  const form = page.locator('form.ie-form')
  await expect(form).toBeVisible()
  await form.locator('select').selectOption('PASS')
  await form.locator('textarea').fill('E2E-AUDIT-20260823 中期检查通过，允许进入成果检查。')
  const [midtermResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/check`)),
    page.getByRole('button', { name: '保存', exact: true }).click()
  ])
  expect(midtermResponse.ok()).toBeTruthy()
  expect((await midtermResponse.json()).code).toBe(0)
}

function finalStep(page) {
  return page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: '成果检查', exact: true }) }).first()
}

async function submitStudentFinal(page, fixture, marker) {
  await loginStudent(page)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  const step = finalStep(page)
  await expect(step).toBeVisible()
  const open = step.getByRole('button', { name: '上传并提交论文', exact: true })
  await expect(open).toBeVisible()
  await open.click()
  const input = step.locator('input[type=file]')
  await expect(input).toHaveCount(1)
  const uploadPromise = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/files'))
  await input.setInputFiles({
    name: `E2E-AUDIT-20260823-${marker}-${fixture.runId}.pdf`,
    mimeType: 'application/pdf',
    buffer: Buffer.from(`%PDF-1.4\n% E2E-AUDIT-20260823 ${marker} ${fixture.runId}\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<<>>\n%%EOF\n`)
  })
  const uploadResponse = await uploadPromise
  expect(uploadResponse.ok(), `upload ${marker} HTTP ${uploadResponse.status()}`).toBeTruthy()
  const uploadBody = await uploadResponse.json()
  expect(uploadBody.code).toBe(0)
  expect(uploadBody.data?.fileId).toBeTruthy()

  const submit = step.getByRole('button', { name: '提交论文成果', exact: true })
  await expect(submit).toBeEnabled()
  const [submitResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/portal/graduation/final/submit')),
    submit.click()
  ])
  expect(submitResponse.ok(), `submit ${marker} HTTP ${submitResponse.status()}`).toBeTruthy()
  const submitBody = await submitResponse.json()
  expect(submitBody.code).toBe(0)
  expect(submitBody.data?.status).toBe('PENDING_REVIEW')
  await expect(step).toContainText(/待审|已提交/)
  return { uploaded: uploadBody.data, submitted: submitBody.data }
}

async function openPendingFinal(page, fixture, { login = true } = {}) {
  if (login) await loginMentor(page)
  await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '成果检查', exact: true })).toBeVisible()
  const row = page.locator('.gd-review-workspace__queue > button').filter({ hasText: fixture.topicTitle }).first()
  await expect(row).toBeVisible()
  await row.click()
  const businessBar = page.locator('.gd-review-workspace__business-bar').first()
  await expect(businessBar).toContainText(fixture.topicTitle)
  const pane = page.locator('.gd-review-workspace__review')
  const evidence = pane.locator('.file-evidence-panel__canonical').first()
  await expect(evidence).toBeVisible()
  await expect(evidence).toContainText(/versionId=/)
  await expect(evidence).toContainText(/SHA=/)
  await expect(page.getByRole('button', { name: /通过当前版本/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /退回当前版本/ })).toBeVisible()
  return { pane, versionEvidence: await evidence.innerText() }
}

async function reviewCurrentFinal(page, action, comment = '') {
  const button = action === 'REJECT'
    ? page.getByRole('button', { name: /退回当前版本/ })
    : page.getByRole('button', { name: /通过当前版本/ })
  if (action === 'REJECT') {
    await page.getByPlaceholder('批阅意见将同步学生端…').fill(comment)
  }
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/finals\/\d+\/review$/.test(new URL(r.url()).pathname)),
    button.click()
  ])
  expect(response.ok(), `review ${action} HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  expect(body.data?.status).toBe(action === 'REJECT' ? 'REJECTED' : 'APPROVED')
  return body.data
}

async function openPlagiarismLedger(page, fixture) {
  await loginAdmin(page)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/plagiarism-ledger`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'plagiarism')
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '答辩与成绩', exact: true })).toBeVisible()
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
  await expect(page.getByRole('button', { name: '查重记录', exact: true })).toBeVisible()
}

async function fillLatestPlagiarismResult(page, rate, reportUrl) {
  const latest = page.locator('.gp-timeline-item').first()
  await expect(latest.getByRole('button', { name: '回填结果', exact: true })).toBeVisible()
  await latest.getByRole('button', { name: '回填结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '回填查重结果', exact: true })).toBeVisible()
  const form = page.locator('form.ie-form')
  const rateInput = form.locator('label').filter({ hasText: '重复率(%)' }).locator('input')
  const reportInput = form.locator('label').filter({ hasText: '报告链接' }).locator('input')
  await rateInput.fill(String(rate))
  await reportInput.fill(reportUrl)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-plagiarism\/\d+\/result$/.test(new URL(r.url()).pathname)),
    page.getByRole('button', { name: '提交', exact: true }).click()
  ])
  expect(response.ok(), `plagiarism result HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  return body.data
}

async function completePlagiarismRecheck(page, fixture) {
  await openPlagiarismLedger(page, fixture)
  const [startResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-plagiarism/${fixture.gdStudentId}/submit`)),
    page.getByRole('button', { name: '发起查重', exact: true }).click()
  ])
  expect(startResponse.ok(), `plagiarism start HTTP ${startResponse.status()}`).toBeTruthy()
  expect((await startResponse.json()).code).toBe(0)

  const firstResult = await fillLatestPlagiarismResult(page, 45, '/api/v1/files/E2E-AUDIT-20260823-plagiarism-report-v1.pdf')
  expect(firstResult.status).toBe('DONE')
  expect(firstResult.overThreshold).toBeTruthy()

  await expect(page.locator('.gp-timeline-item').first()).toContainText(/45/)
  await page.locator('.gp-timeline-item').first().getByRole('button', { name: '申请复查', exact: true }).click()
  await expect(page.getByRole('heading', { name: '申请复查', exact: true })).toBeVisible()
  await page.locator('form.ie-form textarea').fill('E2E-AUDIT-20260823 对高重复率结果申请复查，要求确认引用与代码片段识别。')
  const [disputeResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-plagiarism\/\d+\/dispute$/.test(new URL(r.url()).pathname)),
    page.getByRole('button', { name: '提交', exact: true }).click()
  ])
  expect(disputeResponse.ok(), `plagiarism dispute HTTP ${disputeResponse.status()}`).toBeTruthy()
  expect((await disputeResponse.json()).code).toBe(0)

  const original = page.locator('.gp-timeline-item').filter({ hasText: /45/ }).first()
  await expect(original).toContainText('复查申请')
  const [reviewResponse] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-plagiarism\/\d+\/dispute\/review$/.test(new URL(r.url()).pathname)),
    original.getByRole('button', { name: '通过', exact: true }).click()
  ])
  expect(reviewResponse.ok(), `plagiarism dispute review HTTP ${reviewResponse.status()}`).toBeTruthy()
  const reviewed = await reviewResponse.json()
  expect(reviewed.code).toBe(0)
  expect(reviewed.data?.recheckTaskId).toBeTruthy()

  const recheckResult = await fillLatestPlagiarismResult(page, 12, '/api/v1/files/E2E-AUDIT-20260823-plagiarism-report-recheck.pdf')
  expect(recheckResult.status).toBe('DONE')
  expect(recheckResult.overThreshold).toBeFalsy()
  await expect(page.locator('.gp-timeline-item').first()).toContainText(/12/)

  await page.reload()
  await dismissGuide(page)
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
  await expect(page.locator('.gp-timeline-item').first()).toContainText(/12/)
}

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计成果+查重 Browser First · 退回/重交/复查/定稿通过', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('真实前置 → 初稿退回重交 → 定稿 → 查重超标 → 复查 → 复查合格 → 定稿通过', async ({ page }) => {
    await reachFinalCheckThroughUi(page, fixture)

    const first = await submitStudentFinal(page, fixture, 'draft-v1')
    const firstStaff = await openPendingFinal(page, fixture)
    const firstVersionEvidence = firstStaff.versionEvidence
    await reviewCurrentFinal(page, 'REJECT', 'E2E-AUDIT-20260823 初稿退回：补齐异常场景说明、测试证据和论文格式。')

    const student = new StudentGraduationPage(page, config.studentBaseUrl)
    await resumeStudent(page, student, 'reject readback')
    const rejectedStep = finalStep(page)
    await expect(rejectedStep).toContainText(/驳回|退回|修改/)
    await expect(rejectedStep).toContainText('E2E-AUDIT-20260823')

    const second = await submitStudentFinal(page, fixture, 'draft-v2')
    expect(String(second.uploaded.fileId)).not.toBe(String(first.uploaded.fileId))
    const secondStaff = await openPendingFinal(page, fixture)
    expect(secondStaff.versionEvidence).not.toBe(firstVersionEvidence)
    await reviewCurrentFinal(page, 'APPROVE')

    await resumeStudent(page, student, 'draft approval readback')
    await expect(finalStep(page)).toContainText(/初稿.*通过|已通过/)

    const finalSubmit = await submitStudentFinal(page, fixture, 'final-v1')
    expect(String(finalSubmit.uploaded.fileId)).not.toBe(String(second.uploaded.fileId))
    const beforePlagiarism = await openPendingFinal(page, fixture)
    expect(beforePlagiarism.versionEvidence).not.toBe(secondStaff.versionEvidence)

    await completePlagiarismRecheck(page, fixture)

    await openPendingFinal(page, fixture)
    await reviewCurrentFinal(page, 'APPROVE')

    const resumeResponsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/browser-refresh') && response.request().method() === 'POST'
    )
    await student.open()
    const resumeResponse = await resumeResponsePromise
    expect(resumeResponse.ok(), `student browser-refresh HTTP ${resumeResponse.status()}`).toBeTruthy()
    const completed = finalStep(page)
    await expect(completed).toContainText(/定稿.*通过|定稿已通过|已通过/)
    await expect(completed).toContainText(/12/)
    await expect(completed.getByRole('button', { name: '上传并提交论文', exact: true })).toHaveCount(0)

    await page.reload()
    await expect(finalStep(page)).toContainText(/定稿.*通过|定稿已通过|已通过/)
  })
})