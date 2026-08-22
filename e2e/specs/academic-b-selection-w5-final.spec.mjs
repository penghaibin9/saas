import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StudentLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w5-fixture.json'), 'utf8'))
const MINIAPP_BASE = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'
const secondaryStudent = {
  tenant: config.student.tenant,
  username: fixture.fillerStudentNo,
  password: config.student.password,
}

const pcCourse = fixture.courses.find((row) => row.role === 'PC')
const miniCourse = fixture.courses.find((row) => row.role === 'MINIAPP')
const blockerCourse = fixture.courses.find((row) => row.role === 'BLOCKER')

async function screenshot(page, testInfo, name) {
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready })
  const file = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path: file, contentType: 'image/png' })
}

async function createOpenBatch(testInfo) {
  const admin = await loginApi(config.multiRole)
  const suffix = `${String(Date.now()).slice(-7)}-r${testInfo.retry}`
  const batch = await admin.post('/academic-affairs/selection/batches', {
    batchName: `B-W5-服务器动作闭环-${suffix}`,
    termId: fixture.termId,
    applyScope: {},
  })
  const selectionCourses = new Map()
  for (const row of fixture.courses) {
    const created = await admin.post(`/academic-affairs/selection/batches/${batch.batchId}/courses`, {
      courseId: row.courseId,
      teachingTaskId: row.taskId,
      capacity: row.role === 'BLOCKER' ? 1 : 30,
      minCapacity: 0,
    })
    selectionCourses.set(row.role, { ...row, selectionCourseId: String(created.selectionCourseId) })
  }
  await admin.post(`/academic-affairs/selection/batches/${batch.batchId}/publish`, {})
  await admin.post(`/academic-affairs/selection/batches/${batch.batchId}/open`, {})

  const filler = await loginApi(secondaryStudent)
  await filler.post('/academic-affairs/selection/student/enroll', {
    selectionCourseId: selectionCourses.get('BLOCKER').selectionCourseId,
  })
  return { batch, selectionCourses }
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
  await expect(agreement).toHaveClass(/\bon\b/)
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  expect((await loginResponse).ok()).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

async function pcRow(page, batchName, courseName) {
  const batch = page.locator('.batch-card').filter({ hasText: batchName }).first()
  await expect(batch).toBeVisible({ timeout: 20_000 })
  const row = batch.locator('tr').filter({ hasText: courseName }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  return row
}

async function miniCard(page, batchName, courseName) {
  const group = page.locator('.sl__group').filter({ hasText: batchName }).first()
  await expect(group).toBeVisible({ timeout: 20_000 })
  const card = group.locator('.sl__course').filter({ hasText: courseName }).first()
  await expect(card).toBeVisible({ timeout: 20_000 })
  return card
}

test('Academic B W5 server actions close Student PC + miniapp with blocked/enroll/drop/relogin evidence', async ({ browser }, testInfo) => {
  const { batch } = await createOpenBatch(testInfo)

  const pcContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const pc = await pcContext.newPage()
  const pcLogin = new StudentLoginPage(pc, config.studentBaseUrl)
  await pcLogin.login(config.student)
  await pc.goto(`${config.studentBaseUrl}/academic/selection`)

  const blocked = await pcRow(pc, batch.batchName, blockerCourse.courseName)
  await expect(blocked).toContainText('不可选')
  await expect(blocked).toContainText('课程容量已满')
  await expect(blocked).toContainText('下一步：')
  await expect(blocked.getByRole('button')).toHaveCount(0)
  const pcEligible = await pcRow(pc, batch.batchName, pcCourse.courseName)
  await expect(pcEligible.getByRole('button', { name: '立即选课', exact: true })).toBeVisible()
  await screenshot(pc, testInfo, 'w5-pc-server-actions-before-1440x900')

  const pcPreflight = pc.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/preflight') && response.request().method() === 'POST'
  )
  const pcEnroll = pc.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/enroll') && response.request().method() === 'POST'
  )
  await pcEligible.getByRole('button', { name: '立即选课', exact: true }).click()
  expect((await pcPreflight).ok()).toBeTruthy()
  expect((await pcEnroll).ok()).toBeTruthy()
  const pcSelected = await pcRow(pc, batch.batchName, pcCourse.courseName)
  await expect(pcSelected).toContainText('已选')
  await expect(pcSelected.getByRole('button', { name: '退课', exact: true })).toBeVisible()
  await expect(pcSelected.getByRole('button', { name: '立即选课', exact: true })).toHaveCount(0)
  await screenshot(pc, testInfo, 'w5-pc-selected-drop-action-1440x900')

  await pc.reload()
  const pcAfterRefresh = await pcRow(pc, batch.batchName, pcCourse.courseName)
  await expect(pcAfterRefresh.getByRole('button', { name: '退课', exact: true })).toBeVisible()
  await pcContext.close()

  const miniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const mini = await miniContext.newPage()
  await miniappLogin(mini)
  await mini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/selection`)

  const crossEnd = await miniCard(mini, batch.batchName, pcCourse.courseName)
  await expect(crossEnd).toContainText('已选')
  await expect(crossEnd.locator('.sl__btn')).toHaveText('退课')
  await crossEnd.scrollIntoViewIfNeeded()
  await screenshot(mini, testInfo, 'w5-mini-cross-end-selected-390x844')

  const miniBlocked = await miniCard(mini, batch.batchName, blockerCourse.courseName)
  await expect(miniBlocked).toContainText('不可选')
  await expect(miniBlocked).toContainText('课程容量已满')
  await expect(miniBlocked).toContainText('下一步：')
  const miniBlockedButton = miniBlocked.locator('.sl__btn')
  await expect(miniBlockedButton).toHaveText('不可选')
  await expect(miniBlockedButton).toHaveAttribute('disabled', /^(true|disabled)$/)
  let blockedEnrollRequests = 0
  const countBlockedEnroll = (request) => {
    if (request.url().includes('/api/v1/mobile/academic/selection/enroll') && request.method() === 'POST') {
      blockedEnrollRequests += 1
    }
  }
  mini.on('request', countBlockedEnroll)
  await miniBlockedButton.click({ force: true })
  await mini.waitForTimeout(300)
  mini.off('request', countBlockedEnroll)
  expect(blockedEnrollRequests).toBe(0)

  const miniEligible = await miniCard(mini, batch.batchName, miniCourse.courseName)
  await expect(miniEligible.locator('.sl__btn')).toHaveText('选课')
  const miniPreflight = mini.waitForResponse((response) =>
    response.url().includes('/api/v1/mobile/academic/selection/preflight') && response.request().method() === 'POST'
  )
  const miniEnroll = mini.waitForResponse((response) =>
    response.url().includes('/api/v1/mobile/academic/selection/enroll') && response.request().method() === 'POST'
  )
  await miniEligible.locator('.sl__btn').click()
  expect((await miniPreflight).ok()).toBeTruthy()
  expect((await miniEnroll).ok()).toBeTruthy()
  const miniSelected = await miniCard(mini, batch.batchName, miniCourse.courseName)
  await expect(miniSelected).toContainText('已选')
  await expect(miniSelected.locator('.sl__btn')).toHaveText('退课')
  await miniSelected.scrollIntoViewIfNeeded()
  await screenshot(mini, testInfo, 'w5-mini-selected-server-actions-390x844')

  const miniDropCard = await miniCard(mini, batch.batchName, pcCourse.courseName)
  const miniDrop = mini.waitForResponse((response) =>
    response.url().includes('/api/v1/mobile/academic/selection/drop') && response.request().method() === 'POST'
  )
  await miniDropCard.locator('.sl__btn').click()
  expect((await miniDrop).ok()).toBeTruthy()
  const miniDropped = await miniCard(mini, batch.batchName, pcCourse.courseName)
  await expect(miniDropped).toContainText('已退课')
  await expect(miniDropped.locator('.sl__btn')).toHaveText('选课')
  await miniDropped.scrollIntoViewIfNeeded()
  await screenshot(mini, testInfo, 'w5-mini-drop-reprojected-390x844')

  await mini.reload()
  const miniPersisted = await miniCard(mini, batch.batchName, miniCourse.courseName)
  await expect(miniPersisted.locator('.sl__btn')).toHaveText('退课')
  await miniContext.close()

  const reloginContext = await browser.newContext({ viewport: { width: 1280, height: 720 } })
  const relogin = await reloginContext.newPage()
  const reloginPage = new StudentLoginPage(relogin, config.studentBaseUrl)
  await reloginPage.login(config.student)
  await relogin.goto(`${config.studentBaseUrl}/academic/selection`)
  const miniCourseOnPc = await pcRow(relogin, batch.batchName, miniCourse.courseName)
  await expect(miniCourseOnPc).toContainText('已选')
  await expect(miniCourseOnPc.getByRole('button', { name: '退课', exact: true })).toBeVisible()
  const droppedOnPc = await pcRow(relogin, batch.batchName, pcCourse.courseName)
  await expect(droppedOnPc).toContainText('已退课')
  await expect(droppedOnPc.getByRole('button', { name: '立即选课', exact: true })).toBeVisible()
  await miniCourseOnPc.scrollIntoViewIfNeeded()
  await screenshot(relogin, testInfo, 'w5-pc-cross-end-relogin-1280x720')
  await reloginContext.close()
})
