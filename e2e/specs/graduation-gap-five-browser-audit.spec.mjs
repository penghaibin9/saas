import fs from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StudentGraduationPage } from '../pages/graduation.page.mjs'

const fixture = JSON.parse(fs.readFileSync(new URL('../runtime-logs/gap-five-fixture.json', import.meta.url), 'utf8'))
const studentB = { tenant: config.student.tenant, username: 'E2E20260002', password: config.student.password }
const majorAdmin = { tenant: config.mentor.tenant, username: 'e2e_major_admin', password: config.mentor.password }
const collegeAdmin = { tenant: config.mentor.tenant, username: 'e2e_college_secretary', password: config.mentor.password }

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
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.254.5.${octet}` })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
}

async function loginStudent(page, account, octet) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.254.6.${octet}` })
  await new StudentLoginPage(page, config.studentBaseUrl).login(account)
}

async function pickGraduationStudent(page, label, keyword, visibleText) {
  const field = page.locator('.ie-fld').filter({ hasText: label }).first()
  const picker = field.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(keyword)
  const option = picker.locator('.app-remote-select__option').filter({ hasText: visibleText }).first()
  await expect(option, `${label} option ${visibleText}`).toBeVisible({ timeout: 15000 })
  await option.click()
}

async function confirmVisibleDialog(page, reason) {
  const dialog = page.locator('.app-confirm-dialog,[role=dialog]').filter({ visible: true }).last()
  await expect(dialog).toBeVisible()
  const textarea = dialog.locator('textarea').first()
  if (await textarea.count() && await textarea.isVisible().catch(() => false)) await textarea.fill(reason)
  const confirm = dialog.getByRole('button', { name: /确认|提交|通过|发布|资格|受理|保存/ }).last()
  await expect(confirm).toBeEnabled()
  await confirm.click()
}

async function openStudentGraduation(page, account, octet) {
  await loginStudent(page, account, octet)
  const student = new StudentGraduationPage(page, config.studentBaseUrl)
  await student.open()
  return student
}

test.describe.configure({ retries: 0 })
test.describe.serial('毕业设计剩余五项精准 Browser First · GD-012/016/017', () => {
  test('GD-012 成果互查：管理员分配 → Student B 正式互查 → Student A 整改', async ({ browser }) => {
    test.setTimeout(300000)
    const adminCtx = await browser.newContext()
    const reviewerCtx = await browser.newContext()
    const targetCtx = await browser.newContext()
    const admin = await adminCtx.newPage()
    const reviewer = await reviewerCtx.newPage()
    const target = await targetCtx.newPage()
    try {
      await loginStaff(admin, config.sandboxAdmin, 11)
      await admin.goto(`${config.staffBaseUrl}/admin/graduation/more/peer-assign?batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(admin)
      await expect(admin.getByRole('heading', { name: '分配成果互查', exact: true })).toBeVisible()
      await pickGraduationStudent(admin, '被评学生', fixture.students.A.studentNo, fixture.students.A.name)
      await pickGraduationStudent(admin, '互查学生', fixture.students.B.studentNo, fixture.students.B.name)
      const assignPromise = admin.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-peer-reviews/assign'))
      await admin.getByRole('button', { name: '分配', exact: true }).click()
      const assigned = await assignPromise
      expect(assigned.ok(), `peer assign HTTP ${assigned.status()}`).toBeTruthy()
      const assignBody = await assigned.json()
      expect(assignBody.code, JSON.stringify(assignBody)).toBe(0)
      expect(String(assignBody.data?.gdFinalId || '')).toBe(String(fixture.finalId))

      await openStudentGraduation(reviewer, studentB, 12)
      const peerPanel = reviewer.locator('.gd-peer').filter({ hasText: '成果互查' })
      await expect(peerPanel).toBeVisible({ timeout: 20000 })
      const task = peerPanel.locator('.gd-peer__item').filter({ hasText: fixture.students.A.name }).first()
      await expect(task).toContainText(/待互查/)
      await expect(task).toContainText(/定稿/)
      await expect(task.getByRole('button', { name: '查看任务定稿', exact: true })).toBeEnabled()
      await task.getByPlaceholder('互查意见（至少 5 字）').fill('GD-012 Browser First：冻结定稿内容完整，但建议补充实施风险说明。')
      const reviewPromise = reviewer.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-peer-reviews\/\d+\/submit$/.test(new URL(r.url()).pathname))
      await task.getByRole('button', { name: '提交互查意见', exact: true }).click()
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `peer review HTTP ${reviewed.status()}`).toBeTruthy()
      const reviewBody = await reviewed.json()
      expect(reviewBody.code, JSON.stringify(reviewBody)).toBe(0)
      expect(reviewBody.data?.status).toBe('REVIEWED')

      await openStudentGraduation(target, config.student, 13)
      const targetPanel = target.locator('.gd-peer').filter({ hasText: '成果互查' })
      const rectify = targetPanel.locator('.gd-peer__item').filter({ hasText: /需整改/ }).first()
      await expect(rectify).toBeVisible({ timeout: 20000 })
      await expect(rectify).toContainText('GD-012 Browser First')
      await rectify.getByPlaceholder('整改说明（至少 5 字）').fill('已补充实施风险说明并逐项核对正式定稿，完成本次成果互查整改。')
      const rectifyPromise = target.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-peer-reviews\/\d+\/rectify$/.test(new URL(r.url()).pathname))
      await rectify.getByRole('button', { name: /提交整改|完成整改/ }).click()
      const rectified = await rectifyPromise
      expect(rectified.ok(), `peer rectify HTTP ${rectified.status()}`).toBeTruthy()
      const rectifyBody = await rectified.json()
      expect(rectifyBody.code, JSON.stringify(rectifyBody)).toBe(0)
      expect(rectifyBody.data?.status).toBe('RECTIFIED')
    } finally {
      await adminCtx.close(); await reviewerCtx.close(); await targetCtx.close()
    }
  })

  test('GD-016 优秀成果：导师提名 → 专业复核 → 学院终审发布', async ({ browser }) => {
    test.setTimeout(300000)
    const mentorCtx = await browser.newContext()
    const majorCtx = await browser.newContext()
    const collegeCtx = await browser.newContext()
    const mentor = await mentorCtx.newPage()
    const major = await majorCtx.newPage()
    const college = await collegeCtx.newPage()
    try {
      await loginStaff(mentor, config.mentor, 21)
      await mentor.goto(`${config.staffBaseUrl}/admin/graduation?extension=excellent&batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(mentor)
      await expect(mentor.getByRole('heading', { name: '优秀成果认定', exact: true })).toBeVisible()
      const candidate = mentor.locator('.ext-card').filter({ hasText: fixture.students.A.name }).first()
      await expect(candidate).toContainText(/92 分.*优秀/)
      const nominatePromise = mentor.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-excellent-outcomes/nominate'))
      await candidate.getByRole('button', { name: '导师提名', exact: true }).click()
      await confirmVisibleDialog(mentor, 'GD-016 Browser First 优秀成果提名：成果完整、质量突出、过程证据齐全。')
      const nominated = await nominatePromise
      expect(nominated.ok(), `excellent nominate HTTP ${nominated.status()}`).toBeTruthy()
      expect((await nominated.json()).data?.status).toBe('PENDING_MAJOR')

      await loginStaff(major, majorAdmin, 22)
      await major.goto(`${config.staffBaseUrl}/admin/graduation?extension=excellent&batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(major)
      const majorRow = major.locator('tbody tr').filter({ hasText: fixture.students.A.name }).first()
      await expect(majorRow).toContainText(/待专业/)
      const majorPromise = major.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-excellent-outcomes\/\d+\/major-review$/.test(new URL(r.url()).pathname))
      await majorRow.getByRole('button', { name: '专业通过', exact: true }).click()
      await confirmVisibleDialog(major, 'GD-016 专业复核通过，候选成果符合优秀成果认定标准。')
      const majorReviewed = await majorPromise
      expect(majorReviewed.ok()).toBeTruthy()
      expect((await majorReviewed.json()).data?.status).toBe('PENDING_COLLEGE')

      await loginStaff(college, collegeAdmin, 23)
      await college.goto(`${config.staffBaseUrl}/admin/graduation?extension=excellent&batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(college)
      const collegeRow = college.locator('tbody tr').filter({ hasText: fixture.students.A.name }).first()
      await expect(collegeRow).toContainText(/待学院/)
      const collegePromise = college.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-excellent-outcomes\/\d+\/college-review$/.test(new URL(r.url()).pathname))
      await collegeRow.getByRole('button', { name: '学院发布', exact: true }).click()
      await confirmVisibleDialog(college, 'GD-016 学院终审同意发布优秀成果认定结果。')
      const published = await collegePromise
      expect(published.ok()).toBeTruthy()
      expect((await published.json()).data?.status).toBe('PUBLISHED')
      await college.reload(); await dismissGuide(college)
      await expect(college.locator('tbody tr').filter({ hasText: fixture.students.A.name }).first()).toContainText(/已发布/)
    } finally {
      await mentorCtx.close(); await majorCtx.close(); await collegeCtx.close()
    }
  })

  test('GD-017 风险：真实扫描 → 未选题风险 → 受理 → 记录处理 → 关闭', async ({ page }) => {
    test.setTimeout(240000)
    await loginStaff(page, config.sandboxAdmin, 31)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/risk-archive?panel=risk&batchId=${encodeURIComponent(fixture.batchId)}`)
    await dismissGuide(page)
    await expect(page.getByRole('heading', { name: '问题预警 · 毕设归档 · 毕设统计', exact: true })).toBeVisible()
    const scanPromise = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-risks/scan'))
    await page.getByRole('button', { name: '扫描生成风险项', exact: true }).first().click()
    const scanned = await scanPromise
    expect(scanned.ok(), `risk scan HTTP ${scanned.status()}`).toBeTruthy()
    const scanBody = await scanned.json()
    expect(scanBody.code, JSON.stringify(scanBody)).toBe(0)
    expect(Number(scanBody.data?.scannedStudents || 0)).toBeGreaterThanOrEqual(3)

    const riskRow = page.locator('li.rk-row').filter({ hasText: fixture.students.C.name }).filter({ hasText: '未选题' }).first()
    await expect(riskRow).toBeVisible({ timeout: 20000 })
    await riskRow.click()
    await expect(page.locator('.rk-pane')).toContainText(fixture.students.C.studentNo)

    const acceptPromise = page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-risks\/\d+\/accept$/.test(new URL(r.url()).pathname))
    await page.getByRole('button', { name: '受理', exact: true }).click()
    const accepted = await acceptPromise
    expect(accepted.ok()).toBeTruthy()
    expect((await accepted.json()).data?.status).toBe('PROCESSING')

    await page.getByRole('button', { name: '记录处理', exact: true }).click()
    const processDialog = page.locator('.app-confirm-dialog,[role=dialog]').last()
    await expect(processDialog).toBeVisible()
    await processDialog.locator('textarea').fill('GD-017 已联系学生并确认选题安排，记录处置过程。')
    const processPromise = page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-risks\/\d+\/process$/.test(new URL(r.url()).pathname))
    await processDialog.getByRole('button', { name: /确认|保存|提交/ }).last().click()
    const processed = await processPromise
    expect(processed.ok()).toBeTruthy()
    expect((await processed.json()).data?.status).toBe('PROCESSING')
    await expect(page.locator('.rk-pane')).toContainText('已联系学生')

    await page.getByRole('button', { name: '关闭风险', exact: true }).click()
    const closeDialog = page.locator('.app-confirm-dialog,[role=dialog]').last()
    await expect(closeDialog).toBeVisible()
    await closeDialog.locator('textarea').fill('GD-017 补测完成：风险已人工处置并形成完整关闭留痕。')
    const closePromise = page.waitForResponse((r) => r.request().method() === 'POST' && /\/graduation\/gd-risks\/\d+\/close$/.test(new URL(r.url()).pathname))
    await closeDialog.getByRole('button', { name: /确认|关闭|提交/ }).last().click()
    const closed = await closePromise
    expect(closed.ok()).toBeTruthy()
    expect((await closed.json()).data?.status).toBe('CLOSED')
    await expect(page.locator('.rk-pane')).toContainText('该风险已关闭')
  })
})
