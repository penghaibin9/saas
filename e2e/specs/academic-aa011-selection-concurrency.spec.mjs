import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w5-fixture.json'), 'utf8'))
const prereq = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-aa011-prereq.json'), 'utf8'))
const runtimePath = path.resolve(here, '../academic-aa011-runtime.json')
const MINIAPP_BASE = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'
const mainStudent = config.student
const fillerStudent = {
  tenant: config.student.tenant,
  username: fixture.fillerStudentNo,
  password: config.student.password,
}
const raceCourse = prereq.race
const conflictCourse = prereq.conflict

async function screenshot(page, testInfo, name) {
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready })
  const file = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path: file, contentType: 'image/png' })
}

async function dismissGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1_500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    const skip = page.getByRole('button', { name: '跳过引导' })
    if (await skip.count()) await skip.click()
  }
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
}

async function selectBatch(page, name) {
  const item = page.locator('.aasel-batches > .aasel-batch').filter({ hasText: name }).first()
  await expect(item).toBeVisible({ timeout: 20_000 })
  await item.click()
  await expect(page.locator('.aasel-detail')).toContainText(name)
}

async function expectBatchStatus(page, label) {
  await expect(page.locator('.aasel-hero-topline')).toContainText(label, { timeout: 20_000 })
}

async function lifecycle(page, actionLabel, apiFragment) {
  const preflight = page.waitForResponse((response) =>
    response.url().includes('/selection/batches/') &&
    response.url().includes('/preflight') &&
    response.request().method() === 'GET'
  )
  await page.getByRole('button', { name: actionLabel, exact: true }).click()
  const checked = await preflight
  expect(checked.ok(), `${actionLabel} preflight HTTP ${checked.status()}`).toBeTruthy()
  const preflightBody = await checked.json()
  expect(preflightBody?.data?.allowed, `${actionLabel} preflight: ${JSON.stringify(preflightBody)}`).toBeTruthy()

  const dialog = page.locator('.app-confirm-dialog')
  await expect(dialog).toBeVisible()
  const command = page.waitForResponse((response) =>
    response.url().includes(apiFragment) && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  const result = await command
  expect(result.ok(), `${actionLabel} command HTTP ${result.status()}`).toBeTruthy()
  const body = await result.json()
  expect(body?.code, `${actionLabel} command: ${JSON.stringify(body)}`).toBe(0)
}

async function createBatchThroughStaffUi(page, testInfo) {
  const batchName = `AA-011最后名额并发-${String(Date.now()).slice(-8)}-r${testInfo.retry}`
  await page.getByRole('button', { name: '新建批次', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '新建选课批次' })
  await expect(drawer).toBeVisible()
  await drawer.locator('input').first().fill(batchName)
  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/academic-affairs/selection/batches') &&
    response.request().method() === 'POST'
  )
  await drawer.getByRole('button', { name: '创建', exact: true }).click()
  const response = await responsePromise
  expect(response.ok(), `create batch HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body?.code, JSON.stringify(body)).toBe(0)
  const batchId = String(body?.data?.batchId || '')
  expect(batchId).toBeTruthy()
  await selectBatch(page, batchName)
  return { batchId, batchName }
}

async function addCourseThroughStaffUi(page, batchId, course, capacity) {
  await page.getByRole('button', { name: /添加课程/ }).click()
  const drawer = page.getByRole('dialog', { name: '添加可选课程' })
  await expect(drawer).toBeVisible()
  const picker = drawer.locator('.app-remote-select').first()
  await picker.getByRole('combobox').click()
  const search = picker.locator('.app-remote-select__search-el')
  await search.fill(course.courseCode)
  const option = picker.getByRole('option').filter({ hasText: course.courseName }).first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
  await expect(picker.locator('.app-remote-select__single')).toContainText(course.courseName)

  const numeric = drawer.locator('input')
  await expect(numeric).toHaveCount(2)
  await numeric.nth(0).fill(String(capacity))
  await numeric.nth(1).fill('0')

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes(`/academic-affairs/selection/batches/${batchId}/courses`) &&
    response.request().method() === 'POST'
  )
  await drawer.getByRole('button', { name: '添加', exact: true }).click()
  const response = await responsePromise
  expect(response.ok(), `add course HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body?.code, JSON.stringify(body)).toBe(0)
  return String(body?.data?.selectionCourseId || '')
}

async function studentPage(browser, account) {
  const context = await browser.newContext({ viewport: { width: 1365, height: 820 } })
  const page = await context.newPage()
  const login = new StudentLoginPage(page, config.studentBaseUrl)
  await login.login(account)
  await page.goto(`${config.studentBaseUrl}/academic/selection`)
  return { context, page }
}

async function pcRow(page, batchName, courseName) {
  const batch = page.locator('.batch-card').filter({ hasText: batchName }).first()
  await expect(batch).toBeVisible({ timeout: 20_000 })
  const row = batch.locator('tr').filter({ hasText: courseName }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  return row
}

async function enrollByButton(page, batchName, courseName) {
  const row = await pcRow(page, batchName, courseName)
  const button = row.getByRole('button', { name: /立即选课|立即补选/ }).first()
  await expect(button).toBeVisible({ timeout: 20_000 })
  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/enroll') &&
    response.request().method() === 'POST'
  )
  await button.click()
  const response = await responsePromise
  const body = await response.json().catch(() => ({}))
  expect(response.ok(), `enroll HTTP ${response.status()} ${JSON.stringify(body)}`).toBeTruthy()
  expect(body?.code, JSON.stringify(body)).toBe(0)
  return body
}

async function dropByButton(page, batchName, courseName) {
  await page.reload()
  const row = await pcRow(page, batchName, courseName)
  const button = row.getByRole('button', { name: '退课', exact: true })
  await expect(button).toBeVisible({ timeout: 20_000 })
  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/drop') &&
    response.request().method() === 'POST'
  )
  await button.click()
  const response = await responsePromise
  const body = await response.json().catch(() => ({}))
  expect(response.ok(), `drop HTTP ${response.status()} ${JSON.stringify(body)}`).toBeTruthy()
  expect(body?.code, JSON.stringify(body)).toBe(0)
}

async function miniappLogin(page) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/student/index`)
  const authCard = page.locator('.auth-card')
  await expect(authCard).toBeVisible({ timeout: 20_000 })
  const fields = authCard.getByRole('textbox')
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  const agreement = authCard.locator('.agreement__box').first()
  await agreement.click()
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  expect((await loginResponse).ok()).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

async function miniCard(page, batchName, courseName) {
  const group = page.locator('.sl__group').filter({ hasText: batchName }).first()
  await expect(group).toBeVisible({ timeout: 20_000 })
  const card = group.locator('.sl__course').filter({ hasText: courseName }).first()
  await expect(card).toBeVisible({ timeout: 20_000 })
  return card
}

test('AA-011 Staff PC → two Student PCs last-seat race → Mini parity → locked roster', async ({ browser }, testInfo) => {
  const staffContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const staff = await staffContext.newPage()
  await loginAcademicAdmin(staff)
  await staff.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
  await dismissGuide(staff)

  const batch = await createBatchThroughStaffUi(staff, testInfo)
  const raceSelectionCourseId = await addCourseThroughStaffUi(staff, batch.batchId, raceCourse, 1)
  expect(raceSelectionCourseId).toBeTruthy()
  const conflictSelectionCourseId = await addCourseThroughStaffUi(staff, batch.batchId, conflictCourse, 20)
  expect(conflictSelectionCourseId).toBeTruthy()
  await lifecycle(staff, '发布', `/selection/batches/${batch.batchId}/publish`)
  await expectBatchStatus(staff, '已发布')
  await lifecycle(staff, '开选', `/selection/batches/${batch.batchId}/open`)
  await expectBatchStatus(staff, '选课中')
  await screenshot(staff, testInfo, 'aa011-staff-open-capacity-one-1440x900')

  const main = await studentPage(browser, mainStudent)
  const filler = await studentPage(browser, fillerStudent)
  const mainRace = await pcRow(main.page, batch.batchName, raceCourse.courseName)
  const fillerRace = await pcRow(filler.page, batch.batchName, raceCourse.courseName)
  await expect(mainRace.getByRole('button', { name: '立即选课', exact: true })).toBeVisible()
  await expect(fillerRace.getByRole('button', { name: '立即选课', exact: true })).toBeVisible()

  // Let both visible buttons complete their real preflight, then release the two actual
  // enroll HTTP writes together.  Starting the backend with two workers makes the DB row
  // lock/conditional capacity update, not a JS test stub, the shared authority.
  const barrier = { arrivals: 0, release: null, resolve: null }
  barrier.release = new Promise((resolve) => { barrier.resolve = resolve })
  const holdEnroll = async (route) => {
    barrier.arrivals += 1
    if (barrier.arrivals === 2) barrier.resolve()
    await Promise.race([
      barrier.release,
      new Promise((_, reject) => setTimeout(() => reject(new Error('AA-011 enroll barrier timed out')), 15_000)),
    ])
    await route.continue()
  }
  await main.page.route('**/portal/academic/course-selection/enroll', holdEnroll)
  await filler.page.route('**/portal/academic/course-selection/enroll', holdEnroll)

  const mainResponsePromise = main.page.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/enroll') && response.request().method() === 'POST'
  )
  const fillerResponsePromise = filler.page.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/enroll') && response.request().method() === 'POST'
  )
  await Promise.all([
    mainRace.getByRole('button', { name: '立即选课', exact: true }).click(),
    fillerRace.getByRole('button', { name: '立即选课', exact: true }).click(),
  ])
  const [mainResponse, fillerResponse] = await Promise.all([mainResponsePromise, fillerResponsePromise])
  await main.page.unroute('**/portal/academic/course-selection/enroll', holdEnroll)
  await filler.page.unroute('**/portal/academic/course-selection/enroll', holdEnroll)
  expect(barrier.arrivals, 'both browser writes must reach the enroll barrier').toBe(2)

  const mainBody = await mainResponse.json().catch(() => ({}))
  const fillerBody = await fillerResponse.json().catch(() => ({}))
  const mainWon = mainResponse.ok() && mainBody?.code === 0
  const fillerWon = fillerResponse.ok() && fillerBody?.code === 0
  expect([mainWon, fillerWon].filter(Boolean)).toHaveLength(1)
  const losingBody = mainWon ? fillerBody : mainBody
  expect(String(losingBody?.message || JSON.stringify(losingBody))).toContain('容量已满')

  const winnerAccount = mainWon ? mainStudent : fillerStudent
  const winnerApi = await loginApi(winnerAccount)
  await expect(winnerApi.post('/academic-affairs/selection/student/enroll', {
    selectionCourseId: raceSelectionCourseId,
  })).rejects.toThrow(/已选|重复|有效选课/)

  await main.page.reload()
  await filler.page.reload()
  await screenshot(main.page, testInfo, 'aa011-race-main-after-last-seat-1365x820')
  await screenshot(filler.page, testInfo, 'aa011-race-filler-after-last-seat-1365x820')

  // Re-open the released seat through real UI and finish with the main student selected.
  if (mainWon) {
    await dropByButton(main.page, batch.batchName, raceCourse.courseName)
    await filler.page.reload()
    await enrollByButton(filler.page, batch.batchName, raceCourse.courseName)
    await dropByButton(filler.page, batch.batchName, raceCourse.courseName)
    await main.page.reload()
    await enrollByButton(main.page, batch.batchName, raceCourse.courseName)
  } else {
    await dropByButton(filler.page, batch.batchName, raceCourse.courseName)
    await main.page.reload()
    await enrollByButton(main.page, batch.batchName, raceCourse.courseName)
  }

  await main.page.reload()
  const mainFinalRace = await pcRow(main.page, batch.batchName, raceCourse.courseName)
  await expect(mainFinalRace).toContainText('已选')
  await expect(mainFinalRace).toContainText('0 / 1')
  await expect(mainFinalRace.getByRole('button', { name: '退课', exact: true })).toBeVisible()

  // Both READY tasks were seeded into the same authoritative schedule slot.  Once the
  // race course is selected, the second course must be projected as blocked by server truth.
  const conflictRow = await pcRow(main.page, batch.batchName, conflictCourse.courseName)
  await expect(conflictRow).toContainText('上课时间冲突')
  await expect(conflictRow.getByRole('button', { name: /立即选课|立即补选/ })).toHaveCount(0)
  await screenshot(main.page, testInfo, 'aa011-main-selected-and-time-conflict-blocked-1365x820')

  // Security overlay: an actual SelectionCourse id from another tenant must not resolve
  // under the student's sandbox-school authority.
  const mainApi = await loginApi(mainStudent)
  await expect(mainApi.post('/academic-affairs/selection/student/enroll', {
    selectionCourseId: prereq.foreignSelectionCourseId,
  })).rejects.toThrow(/不存在|数据范围|无权限/)

  const miniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const mini = await miniContext.newPage()
  await miniappLogin(mini)
  await mini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/selection`)
  const miniRace = await miniCard(mini, batch.batchName, raceCourse.courseName)
  await expect(miniRace).toContainText('已选')
  await expect(miniRace.locator('.sl__btn')).toHaveText('退课')
  await screenshot(mini, testInfo, 'aa011-mini-main-selected-parity-390x844')
  await miniContext.close()

  await staff.reload()
  await dismissGuide(staff)
  await selectBatch(staff, batch.batchName)
  await lifecycle(staff, '截止', `/selection/batches/${batch.batchId}/close`)
  await expectBatchStatus(staff, '已截止')

  // Closed-window hard gate: even a real student token cannot claim the occupied seat.
  const fillerApi = await loginApi(fillerStudent)
  await expect(fillerApi.post('/academic-affairs/selection/student/enroll', {
    selectionCourseId: raceSelectionCourseId,
  })).rejects.toThrow(/不在选课时间|当前.*截止|CLOSED/)

  // The intentionally conflicting zero-enrollment course is a negative-test prerequisite,
  // so dispose of it through the real Staff PC button before the formal roster lock.
  const conflictStaffRow = staff.locator('.aasel-section').filter({ hasText: '可选课程与实时容量' })
    .locator('tr').filter({ hasText: conflictCourse.courseName }).first()
  await expect(conflictStaffRow.getByRole('button', { name: '取消开课', exact: true })).toBeVisible()
  await conflictStaffRow.getByRole('button', { name: '取消开课', exact: true }).click()
  const cancelDialog = staff.locator('.app-confirm-dialog')
  await expect(cancelDialog).toBeVisible()
  await cancelDialog.getByRole('button', { name: '确认', exact: true }).click()
  await expect(conflictStaffRow).toContainText('已取消', { timeout: 20_000 })

  await lifecycle(staff, '锁定名单', `/selection/batches/${batch.batchId}/lock`)
  await expectBatchStatus(staff, '已锁定')

  const raceStaffRow = staff.locator('.aasel-section').filter({ hasText: '可选课程与实时容量' })
    .locator('tr').filter({ hasText: raceCourse.courseName }).first()
  await raceStaffRow.getByRole('button', { name: '名单', exact: true }).click()
  const rosterDrawer = staff.getByRole('dialog', { name: `选课名单 · ${raceCourse.courseName}` })
  await expect(rosterDrawer).toContainText(fixture.mainStudentNo)
  await expect(rosterDrawer).not.toContainText(fixture.fillerStudentNo)
  await screenshot(staff, testInfo, 'aa011-staff-locked-single-roster-1440x900')

  fs.writeFileSync(runtimePath, JSON.stringify({
    productSha: process.env.AA011_PRODUCT_SHA || '',
    tenantId: prereq.tenantId,
    batchId: batch.batchId,
    batchName: batch.batchName,
    raceSelectionCourseId,
    conflictSelectionCourseId,
    raceTaskId: String(raceCourse.taskId),
    raceCourseName: raceCourse.courseName,
    conflictCourseName: conflictCourse.courseName,
    mainStudentNo: fixture.mainStudentNo,
    fillerStudentNo: fixture.fillerStudentNo,
    initialWinner: mainWon ? fixture.mainStudentNo : fixture.fillerStudentNo,
    foreignSelectionCourseId: prereq.foreignSelectionCourseId,
  }, null, 2))

  await main.context.close()
  await filler.context.close()
  await staffContext.close()
})
