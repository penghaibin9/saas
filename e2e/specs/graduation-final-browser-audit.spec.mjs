import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

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
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  await student.signTaskbookIfNeeded()
  await student.submitProposal({
    suffix: `${fixture.runId}-final-prereq`,
    fileName: `E2E-AUDIT-20260823-final-prereq-${fixture.runId}.pdf`
  })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
  const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
  await staff.openProposals('PENDING_REVIEW')
  await staff.selectStudent()
  await staff.approve()
}

async function reachFinalCheckThroughUi(page, fixture) {
  await establishApprovedProposal(page, fixture)

  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
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

  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
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
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
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

async function openPendingFinal(page, fixture) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
  await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '成果检查', exact: true })).toBeVisible()
  const row = page.locator('.fr-row').filter({ hasText: fixture.topicTitle }).first()
  await expect(row).toBeVisible()
  await row.click()
  const pane = page.locator('.fr-pane')
  await expect(pane).toContainText(fixture.topicTitle)
  await expect(pane).toContainText('当前安全版本')
  await expect(pane).toContainText('SHA-256')
  await expect(page.getByRole('button', { name: /通过当前版本/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /退回当前版本/ })).toBeVisible()
  const versionRow = pane.locator('.version-table tbody tr').first()
  await expect(versionRow).toBeVisible()
  return { pane, versionEvidence: await versionRow.innerText() }
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

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计成果 Browser First · 退回/重交/初稿通过/定稿通过', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('真实前置 → 初稿提交 → 退回 → 新 FileVersion 重交 → 初稿通过 → 定稿提交并通过', async ({ page }) => {
    await reachFinalCheckThroughUi(page, fixture)

    const first = await submitStudentFinal(page, fixture, 'draft-v1')
    const firstStaff = await openPendingFinal(page, fixture)
    const firstVersionEvidence = firstStaff.versionEvidence
    await reviewCurrentFinal(page, 'REJECT', 'E2E-AUDIT-20260823 初稿退回：补齐异常场景说明、测试证据和论文格式。')

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentGraduationPage(page, config.studentBaseUrl)
    await student.open()
    const rejectedStep = finalStep(page)
    await expect(rejectedStep).toContainText(/驳回|退回|修改/)
    await expect(rejectedStep).toContainText('E2E-AUDIT-20260823')

    const second = await submitStudentFinal(page, fixture, 'draft-v2')
    expect(String(second.uploaded.fileId)).not.toBe(String(first.uploaded.fileId))
    const secondStaff = await openPendingFinal(page, fixture)
    expect(secondStaff.versionEvidence).not.toBe(firstVersionEvidence)
    await reviewCurrentFinal(page, 'APPROVE')

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await student.open()
    await expect(finalStep(page)).toContainText(/初稿.*通过|已通过/)

    const finalSubmit = await submitStudentFinal(page, fixture, 'final-v1')
    expect(String(finalSubmit.uploaded.fileId)).not.toBe(String(second.uploaded.fileId))
    const finalStaff = await openPendingFinal(page, fixture)
    expect(finalStaff.versionEvidence).not.toBe(secondStaff.versionEvidence)
    await reviewCurrentFinal(page, 'APPROVE')

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await student.open()
    const completed = finalStep(page)
    await expect(completed).toContainText(/定稿.*通过|定稿已通过|已通过/)
    await expect(completed.getByRole('button', { name: '上传并提交论文', exact: true })).toHaveCount(0)

    await page.reload()
    await expect(finalStep(page)).toContainText(/定稿.*通过|定稿已通过|已通过/)
  })
})
