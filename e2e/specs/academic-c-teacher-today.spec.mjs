import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../..')
const backendDir = path.join(repoRoot, 'backend')
const statePath = path.join(backendDir, 'tmp/e2e_academic_c_teacher_today_state.local.json')
const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'
const otherTeacher = {
  tenant: config.mentor.tenant,
  username: 'e2e_advisor_b',
  password: config.mentor.password
}

function runFixture(command) {
  execFileSync('python', ['scripts/e2e_seed_academic_c_teacher_today.py', command], {
    cwd: backendDir,
    env: process.env,
    stdio: 'inherit'
  })
}

function readFixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

async function loginTeacherMini(page, account) {
  await page.goto(`${miniBase}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 15_000 })
}

async function clearMiniSession(page) {
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
}

test.describe.serial('Academic C-W2 · Teacher Today real browser seal', () => {
  let fixture

  test.beforeAll(() => {
    runFixture('seed')
    fixture = readFixture()
  })

  test.afterAll(() => {
    runFixture('cleanup')
  })

  test('APPLIED Today -> create/mark -> sessionId reopen -> refresh/relogin -> role/dataScope negatives', async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await loginTeacherMini(page, config.mentor)

    await page.goto(`${miniBase}/#/pages/teacher/academic-affairs/index`)
    const todayCard = page.locator('.ta__course').filter({ hasText: fixture.courseName }).first()
    await expect(todayCard).toBeVisible({ timeout: 15_000 })
    await expect(todayCard).toContainText('已调课')
    await expect(todayCard).toContainText('去点名')

    await todayCard.click()
    await expect(page).toHaveURL(new RegExp(
      `pages/teacher/academic-affairs/attendance\\?teachingTaskId=${fixture.teachingTaskId}`
    ), { timeout: 10_000 })
    expect(page.url()).toContain(`sessionDate=${fixture.targetDate}`)
    expect(page.url()).toContain(`slotNo=${fixture.slotNo}`)
    expect(page.url()).toContain(`scheduleItemId=${fixture.scheduleItemId}`)
    await expect(page.getByText('按教学任务圈定名单并新建', { exact: true })).toBeEnabled({ timeout: 15_000 })

    const createResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST'
        && url.pathname.endsWith('/api/v1/mobile/teacher/academic/attendance/sessions')
    }, { timeout: 15_000 })
    await page.getByText('按教学任务圈定名单并新建', { exact: true }).click()
    const createResponse = await createResponsePromise
    const createPayload = await createResponse.json()
    expect(createPayload.code, JSON.stringify(createPayload)).toBe(0)
    const sessionId = String(createPayload?.data?.sessionId || '')
    expect(sessionId).toMatch(/^\d+$/)
    await expect(page.getByText(fixture.courseName, { exact: true }).first()).toBeVisible({ timeout: 10_000 })

    await page.goto(`${miniBase}/#/pages/teacher/academic-affairs/index`)
    const reopenCard = page.locator('.ta__course').filter({ hasText: fixture.courseName }).first()
    await expect(reopenCard).toBeVisible({ timeout: 15_000 })
    await expect(reopenCard).toContainText('继续点名')
    await reopenCard.click()
    await expect(page).toHaveURL(new RegExp(`attendance\\?sessionId=${sessionId}$`), { timeout: 10_000 })
    await expect(page.getByText('考勤详情', { exact: true })).toBeVisible({ timeout: 10_000 })
    const studentRow = page.locator('.at__row').filter({ hasText: fixture.studentName }).first()
    await expect(studentRow).toBeVisible()

    const markResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST'
        && url.pathname.endsWith(`/api/v1/mobile/teacher/academic/attendance/sessions/${sessionId}/mark`)
    }, { timeout: 15_000 })
    await studentRow.getByText('缺勤', { exact: true }).click()
    const markResponse = await markResponsePromise
    const markPayload = await markResponse.json()
    expect(markPayload.code, JSON.stringify(markPayload)).toBe(0)
    await expect(studentRow.locator('.at__seg-item.is-active')).toHaveText('缺勤')

    await page.reload()
    await expect(page).toHaveURL(new RegExp(`attendance\\?sessionId=${sessionId}$`))
    await expect(page.getByText(fixture.courseName, { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    const persistedRow = page.locator('.at__row').filter({ hasText: fixture.studentName }).first()
    await expect(persistedRow).toBeVisible()
    await expect(persistedRow.locator('.at__seg-item.is-active')).toHaveText('缺勤')

    await clearMiniSession(page)
    await loginTeacherMini(page, config.mentor)
    await page.goto(`${miniBase}/#/pages/teacher/academic-affairs/attendance?sessionId=${sessionId}`)
    await expect(page.getByText(fixture.courseName, { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    const reloginRow = page.locator('.at__row').filter({ hasText: fixture.studentName }).first()
    await expect(reloginRow).toBeVisible()
    await expect(reloginRow.locator('.at__seg-item.is-active')).toHaveText('缺勤')

    const otherTeacherLogin = await request.post(`${config.apiBaseUrl}/auth/login`, {
      data: {
        loginName: otherTeacher.username,
        password: otherTeacher.password,
        tenantCode: otherTeacher.tenant,
        clientType: 'TEACHER_MINI'
      }
    })
    const otherTeacherAuth = await otherTeacherLogin.json()
    expect(otherTeacherAuth.code, JSON.stringify(otherTeacherAuth)).toBe(0)
    const otherTeacherToken = otherTeacherAuth?.data?.accessToken
    expect(otherTeacherToken).toBeTruthy()
    const blockedResponse = await request.get(
      `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${sessionId}`,
      { headers: { Authorization: `Bearer ${otherTeacherToken}` } }
    )
    const blockedPayload = await blockedResponse.json()
    expect(blockedPayload.code, JSON.stringify(blockedPayload)).not.toBe(0)

    const studentLogin = await request.post(`${config.apiBaseUrl}/auth/login`, {
      data: {
        loginName: config.student.username,
        password: config.student.password,
        tenantCode: config.student.tenant,
        clientType: 'STUDENT_MINI'
      }
    })
    const studentAuth = await studentLogin.json()
    expect(studentAuth.code, JSON.stringify(studentAuth)).toBe(0)
    const studentToken = studentAuth?.data?.accessToken
    expect(studentToken).toBeTruthy()
    const roleNegative = await request.get(
      `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${sessionId}`,
      { headers: { Authorization: `Bearer ${studentToken}` } }
    )
    const rolePayload = await roleNegative.json()
    expect(rolePayload.code, JSON.stringify(rolePayload)).not.toBe(0)
  })
})