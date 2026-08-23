import { readFileSync } from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const fixture = JSON.parse(readFileSync(new URL('../academic-c-grade-browser-fixture.json', import.meta.url), 'utf8'))
const account = (username) => ({ tenant: fixture.tenant, username, password: fixture.password })
const staffBase = config.staffBaseUrl.replace(/\/+$/, '')
const studentBase = config.studentBaseUrl.replace(/\/+$/, '')

function waitForRefresh(page, timeout = 20_000) {
  return page.waitForResponse(
    (r) => r.url().includes('/api/v1/auth/browser-refresh') && r.request().method() === 'POST' && r.status() === 200,
    { timeout }
  )
}

async function dismissGuide(page) {
  const dialog = page.getByRole('dialog', { name: '页面操作引导' })
  if (!(await dialog.isVisible({ timeout: 800 }).catch(() => false))) return
  const skip = dialog.getByRole('button', { name: '跳过引导' })
  if (await skip.isVisible({ timeout: 800 }).catch(() => false)) await skip.click()
}

function attachNetworkSeal(page, label) {
  const failures = []
  const badResponses = []
  page.on('requestfailed', (req) => failures.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`))
  page.on('response', (res) => {
    const status = res.status()
    if (status < 400) return
    const url = res.url()
    // Auth access-token expiry is acceptable only because navigation helpers explicitly require refresh=200.
    if (status === 401 && url.includes('/api/v1/')) return
    // Grade journey intentionally contains no negative business call; all grade/transcript 4xx are unexpected.
    if (url.includes('/api/v1/academic-affairs/grade') || url.includes('/api/v1/portal/academic/transcript')) {
      badResponses.push(`${status} ${res.request().method()} ${url}`)
    }
    if (status >= 500) badResponses.push(`${status} ${res.request().method()} ${url}`)
  })
  return () => {
    expect(failures, `${label}: browser requestfailed must be empty`).toEqual([])
    expect(badResponses, `${label}: no unexpected grade/transcript 4xx or any 5xx`).toEqual([])
  }
}

async function loginStaffAndGoto(page, username, path) {
  const login = new StaffLoginPage(page, staffBase)
  await login.login(account(username))
  const refresh = waitForRefresh(page)
  await page.goto(`${staffBase}${path}`)
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissGuide(page)
}

async function gotoStaff(page, path) {
  const refresh = waitForRefresh(page)
  await page.goto(`${staffBase}${path}`)
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissGuide(page)
}

async function openTeachingTaskPicker(page) {
  const field = page.locator('label.aa-field').filter({ hasText: '教学任务' }).first()
  const combo = field.locator('[role="combobox"]')
  await expect(combo).toBeVisible()
  await combo.click()
  const search = field.locator('input.app-remote-select__search-el')
  await search.fill(fixture.courseName)
  const option = field.locator('[role="option"]').filter({ hasText: fixture.courseName }).first()
  await expect(option).toBeVisible({ timeout: 15_000 })
  await option.click()
}

async function openTaskFromList(page) {
  const row = page.locator('.aa-my-task-item').filter({ hasText: fixture.courseName }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  await row.getByRole('button', { name: '进入' }).click()
  await expect(page.getByText(`录入任务：${fixture.courseName}`, { exact: false })).toBeVisible()
}

async function saveAllScores(page, firstFinal = 88) {
  const rows = page.locator('table.aa-course-table tbody tr')
  await expect(rows).toHaveCount(2)
  const values = [
    { usual: 82, final: firstFinal },
    { usual: 55, final: 50 },
  ]
  for (let i = 0; i < 2; i += 1) {
    const row = rows.nth(i)
    const inputs = row.locator('input[type="number"]')
    await expect(inputs).toHaveCount(2)
    await inputs.nth(0).fill(String(values[i].usual))
    await inputs.nth(1).fill(String(values[i].final))
    const responsePromise = page.waitForResponse((r) =>
      r.url().includes('/api/v1/academic-affairs/grade-tasks/') &&
      r.url().includes('/scores') && r.request().method() === 'POST'
    )
    await row.getByRole('button', { name: '录入' }).click()
    const response = await responsePromise
    expect(response.status()).toBe(200)
    const payload = await response.json()
    expect(payload.code).toBe(0)
  }
}

async function studentTranscriptContext(browser, courseShouldExist) {
  const ctx = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  const page = await ctx.newPage()
  const assertNetwork = attachNetworkSeal(page, courseShouldExist ? 'student-after-publish' : 'student-before-publish')
  try {
    const login = new StudentLoginPage(page, studentBase)
    await login.login(account(fixture.students[0]))
    const refresh = waitForRefresh(page)
    await page.goto(`${studentBase}/academic?tab=grades`)
    await refresh
    await expect(page.getByRole('button', { name: '我的成绩' })).toBeVisible({ timeout: 20_000 })
    await page.getByRole('button', { name: '我的成绩' }).click()
    await expect(page.getByText('我的成绩', { exact: true }).last()).toBeVisible()
    if (courseShouldExist) await expect(page.getByText(fixture.courseName, { exact: true })).toBeVisible({ timeout: 20_000 })
    else await expect(page.getByText(fixture.courseName, { exact: true })).toHaveCount(0)
    assertNetwork()
  } finally {
    await ctx.close()
  }
}

test('Academic C grade: teacher input -> college return -> teacher resubmit -> college approve -> academic publish -> student transcript', async ({ browser }, testInfo) => {
  const teacherCtx = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  const teacherPage = await teacherCtx.newPage()
  const teacherNetwork = attachNetworkSeal(teacherPage, 'teacher-grade')
  let gradeTaskId = ''
  try {
    await loginStaffAndGoto(teacherPage, fixture.teacher, '/admin/academic-affairs/grade-entry')
    await expect(teacherPage.getByText('新建成绩录入任务', { exact: true })).toBeVisible()
    await openTeachingTaskPicker(teacherPage)

    const createPromise = teacherPage.waitForResponse((r) =>
      r.url().includes('/api/v1/academic-affairs/grade-tasks') && r.request().method() === 'POST'
    )
    await teacherPage.getByRole('button', { name: '创建任务' }).click()
    const created = await createPromise
    expect(created.status()).toBe(200)
    const createdPayload = await created.json()
    expect(createdPayload.code).toBe(0)
    gradeTaskId = String(createdPayload.data?.gradeTaskId || createdPayload.data?.taskId || '')
    expect(gradeTaskId).toBeTruthy()
    await testInfo.attach('grade-task-id', { body: gradeTaskId, contentType: 'text/plain' })

    const rosterPromise = teacherPage.waitForResponse((r) =>
      r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/roster`) && r.request().method() === 'GET'
    )
    await teacherPage.getByRole('button', { name: '按正式名单圈定' }).click()
    const rosterResponse = await rosterPromise
    expect(rosterResponse.status()).toBe(200)
    await saveAllScores(teacherPage, 88)

    const submitPromise = teacherPage.waitForResponse((r) =>
      r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/submit`) && r.request().method() === 'POST'
    )
    await teacherPage.getByRole('button', { name: '提交进入学院审核' }).click()
    const submitted = await submitPromise
    expect(submitted.status()).toBe(200)
    expect((await submitted.json()).code).toBe(0)

    // Persistence after a real reload: the submitted task must still be visible and no longer editable.
    await teacherPage.reload()
    await teacherPage.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
    await dismissGuide(teacherPage)
    const submittedRow = teacherPage.locator('.aa-my-task-item').filter({ hasText: fixture.courseName }).first()
    await expect(submittedRow).toContainText('已提交')

    // Before academic publish, a real student portal must not expose the grade.
    await studentTranscriptContext(browser, false)

    const collegeCtx = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const collegePage = await collegeCtx.newPage()
    const collegeNetwork = attachNetworkSeal(collegePage, 'college-review')
    try {
      await loginStaffAndGoto(collegePage, fixture.collegeReviewer, '/admin/academic-affairs/grade-college-review')
      const reviewRow = collegePage.getByRole('row').filter({ hasText: fixture.courseName }).first()
      await expect(reviewRow).toBeVisible({ timeout: 20_000 })
      await reviewRow.getByRole('button', { name: '退回' }).click()
      const dialog = collegePage.getByRole('dialog').filter({ hasText: `退回「${fixture.courseName}」` })
      await expect(dialog).toBeVisible()
      await dialog.locator('textarea.app-confirm-dialog__textarea').fill('浏览器验收退回：请教师复核第一名学生期末卷面分后重新提交')
      const returnPromise = collegePage.waitForResponse((r) =>
        r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/college-review`) && r.request().method() === 'POST'
      )
      await dialog.getByRole('button', { name: '确认退回' }).click()
      const returned = await returnPromise
      expect(returned.status()).toBe(200)
      expect((await returned.json()).code).toBe(0)
      await expect(reviewRow).toHaveCount(0)
      collegeNetwork()
    } finally {
      await collegeCtx.close()
    }

    // Teacher receives the returned task, changes a real score and resubmits through UI.
    await gotoStaff(teacherPage, '/admin/academic-affairs/grade-entry')
    await openTaskFromList(teacherPage)
    await expect(teacherPage.getByText('已被退回：', { exact: false })).toBeVisible()
    const firstRow = teacherPage.locator('table.aa-course-table tbody tr').first()
    const firstInputs = firstRow.locator('input[type="number"]')
    await firstInputs.nth(1).fill('96')
    const rescorePromise = teacherPage.waitForResponse((r) =>
      r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/scores`) && r.request().method() === 'POST'
    )
    await firstRow.getByRole('button', { name: '录入' }).click()
    expect((await rescorePromise).status()).toBe(200)

    const resubmitPromise = teacherPage.waitForResponse((r) =>
      r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/submit`) && r.request().method() === 'POST'
    )
    await teacherPage.getByRole('button', { name: '提交进入学院审核' }).click()
    expect((await resubmitPromise).status()).toBe(200)

    const collegeApproveCtx = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const collegeApprovePage = await collegeApproveCtx.newPage()
    const collegeApproveNetwork = attachNetworkSeal(collegeApprovePage, 'college-approve')
    try {
      await loginStaffAndGoto(collegeApprovePage, fixture.collegeReviewer, '/admin/academic-affairs/grade-college-review')
      const reviewRow = collegeApprovePage.getByRole('row').filter({ hasText: fixture.courseName }).first()
      await expect(reviewRow).toBeVisible({ timeout: 20_000 })
      await reviewRow.getByRole('button', { name: '通过' }).click()
      const approveDialog = collegeApprovePage.getByRole('dialog').filter({ hasText: `通过「${fixture.courseName}」` })
      const approvePromise = collegeApprovePage.waitForResponse((r) =>
        r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/college-review`) && r.request().method() === 'POST'
      )
      await approveDialog.getByRole('button', { name: '确认通过' }).click()
      const approved = await approvePromise
      expect(approved.status()).toBe(200)
      expect((await approved.json()).code).toBe(0)
      collegeApproveNetwork()
    } finally {
      await collegeApproveCtx.close()
    }

    const publishCtx = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const publishPage = await publishCtx.newPage()
    const publishNetwork = attachNetworkSeal(publishPage, 'academic-publish')
    try {
      await loginStaffAndGoto(publishPage, fixture.gradeAdmin, '/admin/academic-affairs/grade-publish')
      const publishRow = publishPage.getByRole('row').filter({ hasText: fixture.courseName }).first()
      await expect(publishRow).toBeVisible({ timeout: 20_000 })
      await publishRow.getByRole('button', { name: '发布' }).click()
      const publishDialog = publishPage.getByRole('dialog').filter({ hasText: `发布「${fixture.courseName}」成绩` })
      await expect(publishDialog).toBeVisible()
      const publishPromise = publishPage.waitForResponse((r) =>
        r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/publish`) && r.request().method() === 'POST'
      )
      await publishDialog.getByRole('button', { name: '确认发布（不可撤销）' }).click()
      const published = await publishPromise
      expect(published.status()).toBe(200)
      const publishedPayload = await published.json()
      expect(publishedPayload.code).toBe(0)
      await publishPage.getByRole('button', { name: '已发布（可归档）' }).click()
      await expect(publishPage.getByRole('row').filter({ hasText: fixture.courseName }).first()).toBeVisible({ timeout: 20_000 })
      publishNetwork()
    } finally {
      await publishCtx.close()
    }

    // After publish the same real student account must see the course in the real Student PC transcript.
    await studentTranscriptContext(browser, true)
    teacherNetwork()
  } finally {
    await teacherCtx.close()
  }
})
