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
    suffix: `${fixture.runId}-midterm`,
    fileName: `E2E-AUDIT-20260823-midterm-proposal-${fixture.runId}.pdf`
  })

  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
  const staff = new StaffGraduationPage(page, config.staffBaseUrl, fixture)
  await staff.openProposals('PENDING_REVIEW')
  await staff.selectStudent()
  await staff.reject('E2E-AUDIT-20260823 开题先退回补充真实中期整改计划')

  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  await student.open()
  await student.expectRejected('E2E-AUDIT-20260823 开题先退回补充真实中期整改计划')
  await student.submitProposal({
    suffix: `${fixture.runId}-midterm-resubmit`,
    fileName: `E2E-AUDIT-20260823-midterm-proposal-resubmit-${fixture.runId}.pdf`
  })

  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
  await staff.openProposals('PENDING_REVIEW')
  await staff.selectStudent()
  await staff.approve()
}

async function advanceGuidingToMidtermThroughAdminUi(page, fixture) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
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
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  const step = page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: '中期检查', exact: true }) }).first()
  await expect(step).toBeVisible()
  await expect(step.getByRole('button', { name: '提交整改', exact: true })).toBeVisible()
  await step.getByRole('button', { name: '提交整改', exact: true }).click()
  const textarea = step.getByPlaceholder('逐项说明已采取的整改措施')
  await expect(textarea).toBeVisible()
  await textarea.fill(text)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/portal/graduation/midterm/rectify')),
    step.getByRole('button', { name: '提交整改', exact: true }).click()
  ])
  expect(response.ok(), `student rectify HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  await expect(step).toContainText(/待复核|已提交|整改/)
}

test.describe.serial('毕业设计中期检查 Browser First · 整改重交闭环', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('开题通过 → 管理员真实推进 → 导师限期整改 → 学生整改 → 复核退回 → 再整改 → 复核通过', async ({ page }) => {
    await establishApprovedProposal(page, fixture)
    await advanceGuidingToMidtermThroughAdminUi(page, fixture)

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await openMidterm(page, fixture)
    await expect(page.getByRole('button', { name: '发起中期检查', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '发起中期检查', exact: true }).click()
    await expect(page.getByText('发起中期检查', { exact: true }).first()).toBeVisible()
    await page.locator('select').first().selectOption('RECTIFY')
    await page.getByRole('button', { name: '7 天后 23:59', exact: true }).click()
    await page.locator('textarea').first().fill('E2E-AUDIT-20260823 中期进度偏慢，要求补齐异常场景、测试证据与阶段说明')
    const [checkResponse] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/check`)),
      page.getByRole('button', { name: '保存', exact: true }).click()
    ])
    expect(checkResponse.ok(), `midterm check HTTP ${checkResponse.status()}`).toBeTruthy()
    expect((await checkResponse.json()).code).toBe(0)

    await studentSubmitRectification(page, `E2E-AUDIT-20260823 第一次整改 ${fixture.runId}：补齐异常路径、补测刷新恢复并完善阶段计划。`)

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await openMidterm(page, fixture)
    await expect(page.getByRole('button', { name: '复核不通过', exact: true })).toBeVisible()
    const [failResponse] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-midterms/${fixture.gdStudentId}/rectify/review`)),
      page.getByRole('button', { name: '复核不通过', exact: true }).click()
    ])
    expect(failResponse.ok(), `midterm review fail HTTP ${failResponse.status()}`).toBeTruthy()
    expect((await failResponse.json()).code).toBe(0)

    await studentSubmitRectification(page, `E2E-AUDIT-20260823 第二次整改 ${fixture.runId}：按复核要求完成补测、修订并提交可追溯说明。`)

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
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

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentGraduationPage(page, config.studentBaseUrl)
    await student.open()
    const midtermStep = page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: '中期检查', exact: true }) }).first()
    await expect(midtermStep).toContainText(/通过/)
    await expect(midtermStep.getByRole('button', { name: '提交整改', exact: true })).toHaveCount(0)
  })
})
