import fs from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StudentGraduationPage } from '../pages/graduation.page.mjs'

const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'
const fixture = JSON.parse(fs.readFileSync(new URL('../runtime-logs/gap-five-fixture.json', import.meta.url), 'utf8'))
const studentB = { tenant: config.student.tenant, username: 'E2E20260002', password: config.student.password }
const majorAdmin = { tenant: config.mentor.tenant, username: 'e2e_major_admin', password: config.mentor.password }
const collegeAdmin = { tenant: config.mentor.tenant, username: 'e2e_college_secretary', password: config.mentor.password }
const conflictGroup = `GD013-冲突组-${fixture.runId}`
const validGroup = `GD013-正式组-${fixture.runId}`

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
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.254.13.${octet}` })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
}

async function chooseMentor(field, keyword, visibleText) {
  const picker = field.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(keyword)
  const option = picker.locator('.app-remote-select__option').filter({ hasText: visibleText }).first()
  await expect(option, `mentor option ${visibleText}`).toBeVisible({ timeout: 15000 })
  await option.click()
}

async function createGroup(page, { name, chairNo, chairName, secretaryNo, secretaryName }) {
  await page.goto(`${config.staffBaseUrl}/admin/graduation/defense/groups/create?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '新增答辩组', exact: true })).toBeVisible()
  await page.getByPlaceholder('如 软件工程专业第一答辩组').fill(name)
  await page.getByPlaceholder('如 实训楼 A301').fill('GD-013 E2E 实训楼 A301')
  await chooseMentor(page.locator('.ie-fld').filter({ hasText: '答辩组长' }).first(), chairNo, chairName)
  await chooseMentor(page.locator('.ie-fld').filter({ hasText: '答辩秘书' }).first(), secretaryNo, secretaryName)
  const createPromise = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups'))
  await page.getByRole('button', { name: '创建', exact: true }).click()
  const created = await createPromise
  expect(created.ok(), `create group ${name} HTTP ${created.status()}`).toBeTruthy()
  const body = await created.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  return String(body.data.id)
}

async function assignStudentB(page) {
  const search = page.getByPlaceholder('搜索姓名')
  const eligiblePromise = page.waitForResponse((r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups/eligible-students'))
  await search.fill(fixture.students.B.name)
  expect((await eligiblePromise).ok()).toBeTruthy()
  const candidate = page.locator('.dg-row--pick').filter({ hasText: fixture.students.B.name }).first()
  await expect(candidate).toBeVisible({ timeout: 15000 })
  await candidate.click()
  const assignPromise = page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/defense-groups\/\d+\/assign$/.test(new URL(r.url()).pathname))
  await page.getByRole('button', { name: /分配所选/ }).click()
  const assigned = await assignPromise
  expect(assigned.ok(), `assign Student B HTTP ${assigned.status()}`).toBeTruthy()
  expect((await assigned.json()).code).toBe(0)
}

async function loginStudentMini(page, username = 'E2E20260002') {
  await page.goto(`${miniBase}/#/pages/login/student/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(username)
  await fields.nth(1).fill(config.student.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.student.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入学生首页', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/student\/home\/index/, { timeout: 20000 })
}

async function confirmExtension(page, reason) {
  const dialog = page.locator('.app-confirm-dialog,[role=dialog]').last()
  await expect(dialog).toBeVisible()
  const textarea = dialog.locator('textarea').first()
  if (await textarea.count() && await textarea.isVisible().catch(() => false)) await textarea.fill(reason)
  const button = dialog.getByRole('button', { name: /确认|通过|批准|排期|提交/ }).last()
  await expect(button).toBeEnabled()
  await button.click()
}

test.describe.configure({ retries: 0 })
test.describe.serial('GD-013 + GD-019 精准补测', () => {
  test('GD-013：真实编排冲突阻断 → 正常建组分配发布 → Student Mini/PC 回读', async ({ browser }) => {
    test.setTimeout(420000)
    const adminCtx = await browser.newContext()
    const miniCtx = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const studentCtx = await browser.newContext()
    const admin = await adminCtx.newPage()
    const mini = await miniCtx.newPage()
    const studentPc = await studentCtx.newPage()
    try {
      await loginStaff(admin, config.sandboxAdmin, 11)

      // Conflict proof: Student B's advisor is A; putting A as chair must mark the assigned student/group conflicted.
      await createGroup(admin, {
        name: conflictGroup,
        chairNo: 'e2e_advisor_a', chairName: 'E2E指导教师A',
        secretaryNo: 'e2e_reviewer', secretaryName: 'E2E评阅教师',
      })
      await assignStudentB(admin)
      await expect(admin.locator('.dg-sec').filter({ hasText: '已分配学生' })).toContainText(/冲突|回避/)
      await admin.getByRole('button', { name: '取消', exact: true }).click()
      const conflictRow = admin.locator('tbody tr').filter({ hasText: conflictGroup }).first()
      await expect(conflictRow).toContainText(/冲突|回避/)
      const conflictPublish = conflictRow.getByRole('button', { name: '发布', exact: true })
      await expect(conflictPublish).toHaveClass(/is-disabled/)

      // Remove B from the conflict group so the canonical same-batch uniqueness remains true.
      await conflictRow.getByRole('button', { name: '编辑', exact: true }).click()
      const assignedSection = admin.locator('.dg-sec').filter({ hasText: '已分配学生' })
      const unassignPromise = admin.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/defense-groups\/\d+\/unassign$/.test(new URL(r.url()).pathname))
      await assignedSection.locator('.dg-row').filter({ hasText: fixture.students.B.name }).getByRole('button', { name: '移出', exact: true }).click()
      expect((await unassignPromise).ok()).toBeTruthy()

      // Valid group: chair B is not Student B's advisor; secretary is the independent reviewer identity.
      await createGroup(admin, {
        name: validGroup,
        chairNo: 'e2e_advisor_b', chairName: 'E2E指导教师B',
        secretaryNo: 'e2e_reviewer', secretaryName: 'E2E评阅教师',
      })
      await assignStudentB(admin)
      await expect(admin.locator('.dg-sec').filter({ hasText: '已分配学生' })).not.toContainText('与评委冲突')
      await admin.getByRole('button', { name: '取消', exact: true }).click()
      const row = admin.locator('tbody tr').filter({ hasText: validGroup }).first()
      await expect(row).toBeVisible()
      const publishPromise = admin.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/defense-groups\/\d+\/publish$/.test(new URL(r.url()).pathname))
      await row.getByRole('button', { name: '发布', exact: true }).click()
      await admin.getByRole('button', { name: '确认发布', exact: true }).click()
      const published = await publishPromise
      expect(published.ok(), `defense publish HTTP ${published.status()}`).toBeTruthy()
      expect((await published.json()).code).toBe(0)
      await expect(row).toContainText('已发布')

      // Student Mini H5 must read the same published schedule through its real page.
      await loginStudentMini(mini)
      await mini.goto(`${miniBase}/#/pages/student/graduation/defense/index`)
      await expect(mini.getByText(validGroup, { exact: true })).toBeVisible({ timeout: 20000 })
      await expect(mini.getByText('已发布', { exact: true })).toBeVisible()
      await expect(mini.getByText('GD-013 E2E 实训楼 A301', { exact: true })).toBeVisible()

      // Student PC reads the same schedule from the graduation workspace.
      await new StudentLoginPage(studentPc, config.studentBaseUrl).login(studentB)
      const student = new StudentGraduationPage(studentPc, config.studentBaseUrl)
      await student.open()
      await expect(studentPc.locator('body')).toContainText(validGroup, { timeout: 20000 })
    } finally {
      await adminCtx.close(); await miniCtx.close(); await studentCtx.close()
    }
  })

  test('GD-013：学生延期申请 → 导师 → 专业 → 学院 → 重新排期', async ({ browser }) => {
    test.setTimeout(420000)
    const studentCtx = await browser.newContext()
    const mentorCtx = await browser.newContext()
    const majorCtx = await browser.newContext()
    const collegeCtx = await browser.newContext()
    const student = await studentCtx.newPage()
    const mentor = await mentorCtx.newPage()
    const major = await majorCtx.newPage()
    const college = await collegeCtx.newPage()
    try {
      await new StudentLoginPage(student, config.studentBaseUrl).login(studentB)
      const workbench = new StudentGraduationPage(student, config.studentBaseUrl)
      await workbench.open()
      const extension = student.locator('.gdep')
      await expect(extension).toBeVisible({ timeout: 20000 })
      await expect(extension).toContainText(/申请延期答辩|延期答辩/)
      await extension.getByPlaceholder('说明延期原因、当前情况和预计准备时间（至少10字）').fill('GD-013 Browser First：因项目现场验证需要延期，预计一周内完成补充准备。')
      const applyPromise = student.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.includes('/graduation/extension/defense-delay'))
      await extension.getByRole('button', { name: '提交延期申请', exact: true }).click()
      const applied = await applyPromise
      expect(applied.ok(), `delay apply HTTP ${applied.status()}`).toBeTruthy()
      await expect(extension).toContainText(/待导师|等待导师/)

      await loginStaff(mentor, config.mentor, 21)
      await mentor.goto(`${config.staffBaseUrl}/admin/graduation?extension=delay&batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(mentor)
      let row = mentor.locator('tbody tr').filter({ hasText: fixture.students.B.name }).first()
      await expect(row).toContainText(/待导师/)
      const advisorPromise = mentor.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-defense-delays\/\d+\/advisor-review$/.test(new URL(r.url()).pathname))
      await row.getByRole('button', { name: '导师通过', exact: true }).click()
      await confirmExtension(mentor, 'GD-013 导师审核通过延期申请。')
      expect((await advisorPromise).ok()).toBeTruthy()

      await loginStaff(major, majorAdmin, 22)
      await major.goto(`${config.staffBaseUrl}/admin/graduation?extension=delay&batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(major)
      row = major.locator('tbody tr').filter({ hasText: fixture.students.B.name }).first()
      await expect(row).toContainText(/待专业/)
      const majorPromise = major.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-defense-delays\/\d+\/major-review$/.test(new URL(r.url()).pathname))
      await row.getByRole('button', { name: '专业通过', exact: true }).click()
      await confirmExtension(major, 'GD-013 专业复核同意延期答辩。')
      expect((await majorPromise).ok()).toBeTruthy()

      await loginStaff(college, collegeAdmin, 23)
      await college.goto(`${config.staffBaseUrl}/admin/graduation?extension=delay&batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(college)
      row = college.locator('tbody tr').filter({ hasText: fixture.students.B.name }).first()
      await expect(row).toContainText(/待学院/)
      const collegePromise = college.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-defense-delays\/\d+\/college-review$/.test(new URL(r.url()).pathname))
      await row.getByRole('button', { name: '学院批准', exact: true }).click()
      await confirmExtension(college, 'GD-013 学院审批同意，进入重新排期。')
      expect((await collegePromise).ok()).toBeTruthy()

      await college.reload(); await dismissGuide(college)
      row = college.locator('tbody tr').filter({ hasText: fixture.students.B.name }).first()
      await expect(row).toContainText(/待排期/)
      const groupSelect = row.locator('select').first()
      const validOption = groupSelect.locator('option').filter({ hasText: validGroup }).first()
      const optionValue = await validOption.getAttribute('value')
      expect(optionValue).toBeTruthy()
      await groupSelect.selectOption(optionValue)
      const date = row.locator('input[type=date]').first()
      await date.fill('2026-09-15')
      const schedulePromise = college.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-defense-delays\/\d+\/schedule$/.test(new URL(r.url()).pathname))
      await row.getByRole('button', { name: '确认排期', exact: true }).click()
      await confirmExtension(college, 'GD-013 延期答辩重新排期确认。')
      const scheduled = await schedulePromise
      expect(scheduled.ok(), `delay schedule HTTP ${scheduled.status()}`).toBeTruthy()
      const scheduledBody = await scheduled.json()
      expect(scheduledBody.data?.status).toBe('SCHEDULED')

      await workbench.open()
      await expect(student.locator('.gdep')).toContainText(/已排期|重新排期/)
      await expect(student.locator('.gdep')).toContainText(validGroup)
    } finally {
      await studentCtx.close(); await mentorCtx.close(); await majorCtx.close(); await collegeCtx.close()
    }
  })

  test('GD-019：通知 + 统计投影 + 答辩 XLSX 真实 UI 导出', async ({ page }) => {
    test.setTimeout(240000)
    await loginStaff(page, config.sandboxAdmin, 31)

    // Delay scheduling intentionally revokes publication, so publish the group again before notification/export evidence.
    await page.goto(`${config.staffBaseUrl}/admin/graduation/defense?batchId=${encodeURIComponent(fixture.batchId)}`)
    await dismissGuide(page)
    let row = page.locator('tbody tr').filter({ hasText: validGroup }).first()
    await expect(row).toBeVisible()
    const publish = row.getByRole('button', { name: '发布', exact: true })
    if (await publish.count() && await publish.isVisible().catch(() => false)) {
      const publishPromise = page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/defense-groups\/\d+\/publish$/.test(new URL(r.url()).pathname))
      await publish.click()
      await page.getByRole('button', { name: '确认发布', exact: true }).click()
      expect((await publishPromise).ok()).toBeTruthy()
      row = page.locator('tbody tr').filter({ hasText: validGroup }).first()
    }

    const notifyPromise = page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/defense-groups\/\d+\/notify$/.test(new URL(r.url()).pathname))
    await row.getByRole('button', { name: '通知', exact: true }).click()
    const notified = await notifyPromise
    expect(notified.ok(), `defense notify HTTP ${notified.status()}`).toBeTruthy()
    const notifyBody = await notified.json()
    expect(notifyBody.code, JSON.stringify(notifyBody)).toBe(0)
    expect(Number(notifyBody.data?.notified || 0)).toBeGreaterThanOrEqual(1)

    // XLSX must be initiated from the real visible export control, not direct API.
    const exportPromise = page.waitForResponse((r) => r.request().method() === 'GET' && /graduation/.test(r.url()) && /export/.test(r.url()))
    await page.getByRole('button', { name: /导出答辩表/ }).click()
    const exported = await exportPromise
    expect(exported.ok(), `defense export HTTP ${exported.status()}`).toBeTruthy()

    // Statistics page must read the state created by GD-012/013/016, rather than a canned dashboard.
    await page.goto(`${config.staffBaseUrl}/admin/graduation/stats-report?batchId=${encodeURIComponent(fixture.batchId)}`)
    await dismissGuide(page)
    await expect(page.getByRole('heading', { name: '毕设统计报表', exact: true })).toBeVisible()
    const peerStats = page.locator('.mp-card').filter({ hasText: '成果互查统计' }).first()
    await expect(peerStats).toBeVisible()
    await expect(peerStats).toContainText(/已整改|总数|1/)
    const gradeStats = page.locator('.mp-card').filter({ hasText: '成绩评定统计' }).first()
    await expect(gradeStats).toBeVisible()
    await expect(gradeStats).toContainText(/优秀数|1/)
  })
})
