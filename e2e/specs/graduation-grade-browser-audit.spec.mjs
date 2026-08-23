import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const gradeAdmin = {
  tenant: config.mentor.tenant,
  username: 'e2e_grade_admin',
  password: config.mentor.password,
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

async function loginStaff(page, account, octet) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.252.0.${octet}` })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
}

async function openGradeWorkspace(page, fixture, octet) {
  await loginStaff(page, gradeAdmin, octet)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/grade-ledger`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'grade')
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '答辩与成绩', exact: true })).toBeVisible()

  const context = page.locator('.gp-context')
  if (!(await context.isVisible().catch(() => false))) {
    const search = page.getByPlaceholder('搜索学生姓名/学号')
    await expect(search).toBeVisible()
    await search.fill(fixture.studentNo)
    const student = page.locator('.gp-stu-item').filter({ hasText: fixture.studentNo }).first()
    await expect(student).toBeVisible()
    await student.click()
  }
  await expect(context).toContainText(fixture.studentNo)
  await page.getByRole('button', { name: '成绩评定', exact: true }).click()
  await expect(page.locator('.gp-panel')).toBeVisible()
}

async function calculate(page, fixture, advisorScore, octet) {
  await openGradeWorkspace(page, fixture, octet)
  await page.getByRole('button', { name: '核算成绩', exact: true }).click()
  await expect(page.getByRole('heading', { name: '核算成绩', exact: true })).toBeVisible()
  const form = page.locator('form.ie-form')
  await form.locator('label').filter({ hasText: '导师分' }).locator('input').fill(String(advisorScore))
  await expect(form.locator('label').filter({ hasText: '评阅分' }).locator('input')).toHaveValue('92')
  await expect(form.locator('label').filter({ hasText: '答辩分' }).locator('input')).toHaveValue('93')
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/calculate`)),
    page.getByRole('button', { name: '提交', exact: true }).click(),
  ])
  expect(response.ok(), `calculate grade HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.status).toBe('CALCULATED')
}

async function returnReview(page, fixture, octet) {
  await openGradeWorkspace(page, fixture, octet)
  await page.getByRole('button', { name: '复核退回', exact: true }).click()
  await expect(page.getByRole('heading', { name: '复核退回', exact: true })).toBeVisible()
  await page.locator('form.ie-form textarea').fill('E2E-AUDIT-20260823 成绩复核退回：请重新核对导师评分依据与最终答辩证据。')
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/review`)),
    page.getByRole('button', { name: '提交', exact: true }).click(),
  ])
  expect(response.ok(), `return grade HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.status).toBe('DRAFT')
}

async function approveAndPublish(page, fixture, octet) {
  await openGradeWorkspace(page, fixture, octet)
  const [review] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/review`)),
    page.getByRole('button', { name: '复核通过', exact: true }).click(),
  ])
  expect(review.ok(), `approve grade HTTP ${review.status()}`).toBeTruthy()
  const reviewBody = await review.json()
  expect(reviewBody.code, JSON.stringify(reviewBody)).toBe(0)
  expect(reviewBody.data?.status).toBe('REVIEWED')
  await expect(page.getByRole('button', { name: '发布成绩', exact: true })).toBeVisible()
  const [published] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/publish`)),
    page.getByRole('button', { name: '发布成绩', exact: true }).click(),
  ])
  expect(published.ok(), `publish grade HTTP ${published.status()}`).toBeTruthy()
  const publishedBody = await published.json()
  expect(publishedBody.code, JSON.stringify(publishedBody)).toBe(0)
  expect(publishedBody.data?.status).toBe('PUBLISHED')
}

async function studentAppeal(page, fixture) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': '10.252.0.90' })
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  await page.goto(`${config.studentBaseUrl}/graduation`)
  await expect(page.getByRole('heading', { name: '按步骤完成我的毕业设计', exact: true })).toBeVisible()
  await expect(page.locator('.gd-grade-box')).toContainText(/综合成绩/)
  await page.getByRole('button', { name: '对成绩有异议？发起更正申诉', exact: true }).click()
  const reason = 'E2E-AUDIT-20260823 成绩申诉：请复核导师评分依据、独立评阅与二次答辩最终记录。'
  await page.getByPlaceholder('说明异议点与依据（至少 5 字）').fill(reason)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/portal/graduation/grade/appeal')),
    page.getByRole('button', { name: '提交成绩申诉', exact: true }).click(),
  ])
  expect(response.ok(), `student grade appeal HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  await expect(page.locator('.gd-grade-box')).toContainText(/成绩申诉待复核|待复核/)
}

async function approveAppeal(page, fixture, octet) {
  await loginStaff(page, gradeAdmin, octet)
  await page.goto(`${config.staffBaseUrl}/admin/graduation/grade-ledger?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)

  // A real operator must be able to discover this queue from the navigation, not know a hidden URL.
  await expect.soft(page.getByText('成绩更正申诉', { exact: true }).first()).toBeVisible()

  await page.goto(`${config.staffBaseUrl}/admin/graduation/more?panel=appeals`)
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '成绩更正申诉', exact: true })).toBeVisible()
  const row = page.locator('tbody tr').filter({ hasText: fixture.studentName }).first()
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: '受理', exact: true }).click()
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-grade-appeals\/[^/]+\/review$/.test(new URL(r.url()).pathname)),
    page.getByRole('button', { name: '受理', exact: true }).last().click(),
  ])
  expect(response.ok(), `approve grade appeal HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.status).toBe('APPROVED')
}

async function manualWithdraw(page, fixture, octet) {
  await openGradeWorkspace(page, fixture, octet)
  await page.getByRole('button', { name: '撤回', exact: true }).click()
  await expect(page.getByRole('heading', { name: '撤回成绩', exact: true })).toBeVisible()
  await page.locator('form.ie-form textarea').fill('E2E-AUDIT-20260823 人工撤回：最终发布前再次核验完整成绩来源证据。')
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/withdraw`)),
    page.getByRole('button', { name: '提交', exact: true }).click(),
  ])
  expect(response.ok(), `withdraw grade HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.status).toBe('WITHDRAWN')
}

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计成绩 Browser First · 核算/复核/发布/申诉/撤回/再发布', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    const admin = await loginApi(config.sandboxAdmin)
    const student = await admin.get(`/graduation/gd-students/${fixture.gdStudentId}`)
    fixture.studentName = String(student?.name || '')
    expect(fixture.studentName).toBeTruthy()
  })

  test('成绩管理员退回重核 → 发布 → 学生申诉 → 受理撤回 → 重发 → 人工撤回 → 最终重发', async ({ page }) => {
    await calculate(page, fixture, 90, 71)
    await returnReview(page, fixture, 72)

    await calculate(page, fixture, 93, 73)
    await approveAndPublish(page, fixture, 74)

    await studentAppeal(page, fixture)
    await approveAppeal(page, fixture, 75)

    await calculate(page, fixture, 94, 76)
    await approveAndPublish(page, fixture, 77)

    await manualWithdraw(page, fixture, 78)
    await calculate(page, fixture, 95, 79)
    await approveAndPublish(page, fixture, 80)

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gp-panel')).toContainText(/已发布/)
    await expect(page.locator('.gp-panel')).toContainText(/94（优秀）|94.*优秀/)
  })
})