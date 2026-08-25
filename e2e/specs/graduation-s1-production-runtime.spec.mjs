import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const miniBase = String(process.env.E2E_MINIAPP_BASE_URL || '').replace(/\/+$/, '')
const publicOrigin = new URL(config.staffBaseUrl).origin

function apiPath(response, pattern) {
  if (response.request().method() !== 'GET' && response.request().method() !== 'POST') return false
  const url = new URL(response.url())
  return url.origin === publicOrigin && pattern.test(url.pathname)
}

async function expectProductionBundle(page, label) {
  const scripts = await page.locator('script[src]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('src') || ''))
  const styles = await page.locator('link[rel="stylesheet"][href]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('href') || ''))
  expect(scripts.some((src) => src.includes('@vite/client')), `${label} must not load Vite dev client`).toBeFalsy()
  expect([...scripts, ...styles].some((src) => /:(5173|5188|5199)(?:\/|$)/.test(src)), `${label} must not reference dev-server ports`).toBeFalsy()
}

async function dismissGuide(page) {
  for (const pattern of [/跳过引导|跳过/, /我知道了/, /已了解/, /开始使用/]) {
    const button = page.getByRole('button', { name: pattern }).first()
    if (await button.count() && await button.isVisible().catch(() => false)) await button.click().catch(() => {})
  }
}

async function loginStudentMini(page) {
  await page.goto(`${miniBase}/#/pages/login/student/index`)
  await expectProductionBundle(page, 'Student Mini H5')
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.student.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  const loginResponse = page.waitForResponse((response) => apiPath(response, /\/api\/v1\/auth\/login$/))
  await page.getByText('进入学生首页', { exact: true }).click()
  const response = await loginResponse
  expect(response.ok(), `Student Mini production login HTTP ${response.status()}`).toBeTruthy()
  await expect(page).toHaveURL(/pages\/student\/home\/index/, { timeout: 30_000 })
}

async function loginTeacherMini(page) {
  await page.goto(`${miniBase}/#/pages/login/teacher/index`)
  await expectProductionBundle(page, 'Teacher Mini H5')
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(config.mentor.username)
  await fields.nth(1).fill(config.mentor.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.mentor.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  const loginResponse = page.waitForResponse((response) => apiPath(response, /\/api\/v1\/auth\/login$/))
  await page.getByText('进入教师工作台', { exact: true }).click()
  const response = await loginResponse
  expect(response.ok(), `Teacher Mini production login HTTP ${response.status()}`).toBeTruthy()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 30_000 })
}

test.describe.configure({ retries: 0 })

test.describe.serial('S1 · Graduation production runtime seal', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('production bundles + HTTPS Nginx + real proxy + two-worker backend keep graduation usable', async ({ browser }) => {
    test.setTimeout(900_000)

    const staffContext = await browser.newContext({ ignoreHTTPSErrors: true })
    const studentContext = await browser.newContext({ ignoreHTTPSErrors: true })
    const studentMiniContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } })
    const teacherMiniContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } })
    const staff = await staffContext.newPage()
    const studentPc = await studentContext.newPage()
    const studentMini = await studentMiniContext.newPage()
    const teacherMini = await teacherMiniContext.newPage()

    try {
      // Staff PC: the browser login itself must traverse the public Nginx origin.
      const staffLoginResponse = staff.waitForResponse((response) => apiPath(response, /\/api\/v1\/auth\/browser-login$/))
      await new StaffLoginPage(staff, config.staffBaseUrl).login(config.sandboxAdmin)
      const staffLogin = await staffLoginResponse
      expect(staffLogin.ok(), `Staff production login HTTP ${staffLogin.status()}`).toBeTruthy()
      await expectProductionBundle(staff, 'Staff PC')

      // Graduation menu/runtime entry.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation`)
      await dismissGuide(staff)
      await expect(staff.getByText('毕业设计中心', { exact: true }).first()).toBeVisible({ timeout: 30_000 })
      await expect(staff.getByText('毕业设计运营总览', { exact: true })).toBeVisible({ timeout: 30_000 })

      // Unified review center: real API through Nginx, then refresh the deep link to prove history fallback.
      const reviewResponse = staff.waitForResponse((response) => apiPath(response, /\/api\/v1\/graduation\/(?:gd-reviews|gd-students|batches)/))
      const reviewUrl = `${config.staffBaseUrl}/admin/graduation/review-tasks?batchId=${encodeURIComponent(fixture.batchId)}`
      await staff.goto(reviewUrl)
      await dismissGuide(staff)
      expect((await reviewResponse).ok(), 'Unified review center must read graduation data through Nginx').toBeTruthy()
      await expect(staff.getByText('论文评阅任务', { exact: true })).toBeVisible({ timeout: 30_000 })
      await expect(staff.locator('[aria-label="评阅队列筛选"]')).toBeVisible({ timeout: 30_000 })
      await staff.reload()
      await dismissGuide(staff)
      await expect(staff).toHaveURL(/\/admin\/graduation\/review-tasks/)
      await expect(staff.locator('[aria-label="评阅队列筛选"]')).toBeVisible({ timeout: 30_000 })

      // Defense scoring and grade ledger production routes must both bootstrap the exact student context.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/defense-scoring?batchId=${encodeURIComponent(fixture.batchId)}&studentId=${encodeURIComponent(fixture.gdStudentId)}`)
      await dismissGuide(staff)
      await expect(staff.getByRole('heading', { name: '答辩与成绩', exact: true })).toBeVisible({ timeout: 30_000 })
      await expect(staff.locator('.gp-context')).toContainText(fixture.studentNo, { timeout: 30_000 })
      await expect(staff.getByRole('button', { name: '答辩评分', exact: true })).toBeVisible()

      await staff.goto(`${config.staffBaseUrl}/admin/graduation/grade-ledger?batchId=${encodeURIComponent(fixture.batchId)}&studentId=${encodeURIComponent(fixture.gdStudentId)}`)
      await dismissGuide(staff)
      await expect(staff.getByRole('heading', { name: '答辩与成绩', exact: true })).toBeVisible({ timeout: 30_000 })
      await expect(staff.locator('.gp-context')).toContainText(fixture.studentNo, { timeout: 30_000 })
      await staff.getByRole('button', { name: '成绩评定', exact: true }).click()
      await expect(staff.locator('.gp-panel')).toBeVisible({ timeout: 30_000 })

      // Student PC: production browser cookie transport, deep-link refresh, upload, in-app preview and download.
      const studentLoginResponse = studentPc.waitForResponse((response) => apiPath(response, /\/api\/v1\/auth\/browser-login$/))
      await new StudentLoginPage(studentPc, config.studentBaseUrl).login(config.student)
      const studentLogin = await studentLoginResponse
      expect(studentLogin.ok(), `Student production login HTTP ${studentLogin.status()}`).toBeTruthy()
      await expectProductionBundle(studentPc, 'Student PC')

      const studentGraduation = new StudentGraduationPage(studentPc, config.studentBaseUrl)
      await studentGraduation.open()
      await expect(studentPc.getByText(fixture.batchName, { exact: true })).toBeVisible({ timeout: 30_000 })
      await expect(studentPc.getByText(fixture.topicTitle, { exact: true })).toBeVisible()
      await expect(studentPc.getByText(fixture.mentorName, { exact: true }).first()).toBeVisible()
      await studentPc.reload()
      await expect(studentPc).toHaveURL(/\/portal\/graduation/)
      await expect(studentPc.getByRole('heading', { name: '按步骤完成我的毕业设计', exact: true })).toBeVisible({ timeout: 30_000 })

      await studentGraduation.signTaskbookIfNeeded()
      const proposalFile = `S1-PROD-${fixture.runId}.pdf`
      await studentGraduation.submitProposal({ suffix: `S1-PROD-${fixture.runId}`, fileName: proposalFile })
      const proposalStep = studentGraduation.step('开题')
      await expect(proposalStep.getByRole('button', { name: '查看当前版', exact: true }).first()).toBeVisible({ timeout: 30_000 })

      await proposalStep.getByRole('button', { name: '查看当前版', exact: true }).first().click()
      const reader = studentPc.getByRole('dialog', { name: '站内文件阅读器', exact: true })
      await expect(reader).toBeVisible({ timeout: 30_000 })
      await expect(reader).toContainText(proposalFile, { timeout: 30_000 })
      await expect(reader.locator('[data-preview-adapter="pdf"]')).toBeVisible({ timeout: 30_000 })
      await expect(reader.locator('canvas').first()).toBeVisible({ timeout: 30_000 })
      await reader.getByRole('button', { name: '关闭阅读器', exact: true }).click()
      await expect(reader).toBeHidden()

      const downloadResponse = studentPc.waitForResponse((response) => apiPath(response, /\/api\/v1\/files\/download\/[^/]+$/))
      await proposalStep.getByRole('button', { name: '下载', exact: true }).first().click()
      const downloaded = await downloadResponse
      expect(downloaded.ok(), `Student production material download HTTP ${downloaded.status()}`).toBeTruthy()

      // Production Mini H5: both student and teacher identities must run from the built bundle, not dev:h5.
      await loginStudentMini(studentMini)
      await studentMini.goto(`${miniBase}/#/pages/student/graduation/index`)
      await expect(studentMini.getByText(fixture.batchName, { exact: true })).toBeVisible({ timeout: 30_000 })
      await expect(studentMini.getByText(fixture.topicTitle, { exact: true })).toBeVisible()
      await expect(studentMini.getByText(fixture.mentorName, { exact: false }).first()).toBeVisible()

      await loginTeacherMini(teacherMini)
      const taskbookResponse = teacherMini.waitForResponse((response) => apiPath(response, /\/api\/v1\/mobile\/teacher\/graduation\/taskbooks/))
      await teacherMini.goto(`${miniBase}/#/pages/teacher/graduation-taskbook/index`)
      const taskbooks = await taskbookResponse
      expect(taskbooks.ok(), `Teacher Mini production taskbook read HTTP ${taskbooks.status()}`).toBeTruthy()
      await expect(teacherMini.getByText(fixture.batchName, { exact: true })).toBeVisible({ timeout: 30_000 })
      await expect(teacherMini.getByText(fixture.studentNo, { exact: false }).first()).toBeVisible({ timeout: 30_000 })

      await test.info().attach('s1-production-runtime-identity.json', {
        body: Buffer.from(JSON.stringify({
          productSha: process.env.E2E_EXPECTED_SHA,
          publicOrigin,
          batchId: fixture.batchId,
          batchName: fixture.batchName,
          gdStudentId: fixture.gdStudentId,
          studentNo: fixture.studentNo,
          topicTitle: fixture.topicTitle,
          mentorName: fixture.mentorName,
        }, null, 2)),
        contentType: 'application/json',
      })
    } finally {
      await Promise.all([
        staffContext.close(),
        studentContext.close(),
        studentMiniContext.close(),
        teacherMiniContext.close(),
      ])
    }
  })
})
