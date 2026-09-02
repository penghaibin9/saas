import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const actorIp = {
  student: '10.253.0.11',
  mentor: '10.253.0.21',
  admin: '10.253.0.31',
}

async function loginStudent(page) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': actorIp.student })
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
}

async function loginStaff(page, account, ip) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': ip })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
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

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function resubmitRejectedProposalFromFeedback(page, fixture) {
  const feedback = page.locator('section').filter({ hasText: 'W7.5 · Student PC Feedback / Resubmit' }).first()
  await expect(feedback).toBeVisible()
  await expect(feedback.getByRole('heading', { name: '整改后重交开题报告', exact: true })).toBeVisible()
  await expect(feedback).toContainText('E2E-AUDIT-20260823 开题先退回补充真实中期整改计划')

  const background = feedback.getByLabel('选题背景与研究依据', { exact: true })
  const plan = feedback.getByLabel('研究方案与进度计划', { exact: true })
  const outcome = feedback.getByLabel('预期成果', { exact: true })
  await expect(background).toBeVisible()
  await expect(plan).toBeVisible()
  await background.fill(`E2E-GD020 背景 ${fixture.runId}-midterm-resubmit：通过反馈整改入口生成新版本。`)
  await plan.fill(`E2E-GD020 计划 ${fixture.runId}-midterm-resubmit：保留旧版冻结证据并重新送审。`)
  if (await outcome.count()) await outcome.fill(`E2E-GD020 成果 ${fixture.runId}-midterm-resubmit：验证反馈整改闭环。`)

  const fileInput = feedback.locator('input[type=file]')
  await expect(fileInput).toHaveCount(1)
  await fileInput.setInputFiles({
    name: `E2E-AUDIT-20260823-midterm-proposal-resubmit-${fixture.runId}.pdf`,
    mimeType: 'application/pdf',
    buffer: buildPreviewablePdf(`${fixture.runId}-midterm-proposal-resubmit`)
  })

  const submit = feedback.getByRole('button', { name: '整改完成，重新提交开题报告', exact: true })
  await expect(submit).toBeEnabled()
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/portal/graduation/proposal/submit')),
    submit.click()
  ])
  expect(response.ok(), `feedback proposal resubmit HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)

  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await expect(student.step('开题')).toContainText(/待审核|待审阅|已提交/)
  await expect(feedback.getByRole('heading', { name: '整改后重交开题报告', exact: true })).toHaveCount(0)
}

async function establishApprovedProposal(page, fixture) {
  await loginStudent(page)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  await student.signTaskbookIfNeeded()
  await student.submitProposal({
    suffix: `${fixture.runId}-midterm`,
    fileName: `E2E-AUDIT-20260823-midterm-proposal-${fixture.runId}.pdf`
  })

  await loginStaff(page, config.mentor, actorIp.mentor)
  const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
  await staff.openProposals('PENDING_REVIEW')
  await staff.selectStudent()
  await staff.reject('E2E-AUDIT-20260823 开题先退回补充真实中期整改计划')

  await loginStudent(page)
  await student.open()
  await student.expectRejected('E2E-AUDIT-20260823 开题先退回补充真实中期整改计划')
  await resubmitRejectedProposalFromFeedback(page, fixture)

  await loginStaff(page, config.mentor, actorIp.mentor)
  await staff.openProposals('PENDING_REVIEW')
  await staff.selectStudent()
  await staff.approve()
}

async function advanceGuidingToMidtermThroughAdminUi(page, fixture) {
  await loginStaff(page, config.sandboxAdmin, actorIp.admin)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/students/${fixture.gdStudentId}`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)

  const stage = page.locator('.gsd-summary__item').filter({ hasText: '当前节点' }).first()
  await expect(stage).toContainText('指导中')
  await page.getByRole('button', { name: '推进节点', exact: true }).click()
  await expect(page.getByText('推进节点', { exact: true }).last()).toBeVisible()

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-students/${fixture.gdStudentId}/stage`)),
    page.getByRole('button', { name: '推进', exact: true }).click()
  ])
  expect(response.ok(), `stage advance HTTP ${response.status()}`).toBeTruthy()
  expect((await response.json()).code).toBe(0)
  await expect(stage).toContainText('中期检查')

  await page.reload()
  await dismissGuide(page)
  await expect(page.locator('.gsd-summary__item').filter({ hasText: '当前节点' }).first()).toContainText('中期检查')
}

async function openMidterm(page, fixture) {
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/process`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'midterm')
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '过程指导', exact: true })).toBeVisible()
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
}

async function studentSubmitRectification(page, text) {
  await loginStudent(page)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  const step = page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: '中期检查', exact: true }) }).first()
  await expect(step).toBeVisible()
  const openRectify = step.getByRole('button', { name: '提交整改说明', exact: true }).first()
  await expect(openRectify).toBeVisible()
  await openRectify.click()
  const textarea = step.getByPlaceholder('逐项说明已采取的整改措施')
  await expect(textarea).toBeVisible()
  await textarea.fill(text)
  const submitRectify = step.getByRole('button', { name: '提交整改', exact: true }).last()
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/portal/graduation/midterm/rectify')),
    submitRectify.click()
  ])
  expect(response.ok(), `student rectify HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  await expect(step).toContainText(/待复核|已提交|整改/)
}

// 这是会真实写 MySQL 的有状态 Journey；失败后不能在同一外部 fixture 上自动重跑，
// 否则第一次已提交的数据会污染第二次并制造假红灯。新的 workflow run 会得到全新 MySQL service。
test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计中期检查 Browser First · 整改重交闭环', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('开题通过 → 管理员真实推进 → 导师限期整改 → 学生整改 → 复核退回 → 再整改 → 复核通过', async ({ page }) => {
    await establishApprovedProposal(page, fixture)
    await advanceGuidingToMidtermThroughAdminUi(page, fixture)

    await loginStaff(page, config.mentor, actorIp.mentor)
    await openMidterm(page, fixture)
    await expect(page.getByRole('button', { name: '发起中期检查', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '发起中期检查', exact: true }).click()
    await expect(page.getByText('发起中期检查', { exact: true }).first()).toBeVisible()

    const midtermForm = page.locator('form.ie-form')
    await expect(midtermForm).toBeVisible()
    await midtermForm.locator('select').selectOption('RECTIFY')
    await midtermForm.getByRole('button', { name: '7 天后 23:59', exact: true }).click()
    await midtermForm.locator('textarea').fill('E2E-AUDIT-20260823 中期进度偏慢，要求补齐异常场景、测试证据与阶段说明')
    const [checkResponse] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/check`)),
      page.getByRole('button', { name: '保存', exact: true }).click()
    ])
    expect(checkResponse.ok(), `midterm check HTTP ${checkResponse.status()}`).toBeTruthy()
    expect((await checkResponse.json()).code).toBe(0)

    await studentSubmitRectification(page, `E2E-AUDIT-20260823 第一次整改 ${fixture.runId}：补齐异常路径、补测刷新恢复并完善阶段计划。`)

    await loginStaff(page, config.mentor, actorIp.mentor)
    await openMidterm(page, fixture)
    await expect(page.getByRole('button', { name: '复核不通过', exact: true })).toBeVisible()
    const [failResponse] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/rectify/review`)),
      page.getByRole('button', { name: '复核不通过', exact: true }).click()
    ])
    expect(failResponse.ok(), `midterm review fail HTTP ${failResponse.status()}`).toBeTruthy()
    expect((await failResponse.json()).code).toBe(0)

    await studentSubmitRectification(page, `E2E-AUDIT-20260823 第二次整改 ${fixture.runId}：按复核要求完成补测、修订并提交可追溯说明。`)

    await loginStaff(page, config.mentor, actorIp.mentor)
    await openMidterm(page, fixture)
    await expect(page.getByRole('button', { name: '整改复核通过', exact: true })).toBeVisible()
    const [passResponse] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/rectify/review`)),
      page.getByRole('button', { name: '整改复核通过', exact: true }).click()
    ])
    expect(passResponse.ok(), `midterm review pass HTTP ${passResponse.status()}`).toBeTruthy()
    expect((await passResponse.json()).code).toBe(0)
    await expect(page.locator('.gp-panel')).toContainText(/整改.*通过|复核.*通过|已通过/)

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gp-panel')).toContainText(/整改.*通过|复核.*通过|已通过/)

    await loginStudent(page)
    const student = new StudentGraduationPage(page, config.studentBaseUrl)
    await student.open()
    const midtermStep = page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: '中期检查', exact: true }) }).first()
    await expect(midtermStep).toContainText(/通过/)
    await expect(midtermStep.getByRole('button', { name: '提交整改说明', exact: true })).toHaveCount(0)
  })
})