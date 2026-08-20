import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w4-formation-fixture.json'), 'utf8'))

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

async function createSelectionBatch(testInfo) {
  const api = await loginApi(config.multiRole)
  const suffix = `${String(Date.now()).slice(-7)}-r${testInfo.retry}`
  const batch = await api.post('/academic-affairs/selection/batches', {
    batchName: `B-W4-Formation闭环-${suffix}`,
    termId: fixture.termId,
    applyScope: {}
  })
  expect(String(batch?.termId || '')).toBe(fixture.termId)
  return batch
}

async function selectBatch(page, name) {
  const item = page.locator('.aasel-batches > .aasel-batch').filter({ hasText: name }).first()
  await expect(item).toBeVisible({ timeout: 20_000 })
  await item.click()
  await expect(page.locator('.aasel-detail')).toContainText(name)
}

async function openAddCourse(page) {
  await page.getByRole('button', { name: '+ 添加课程', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '添加可选课程' })
  await expect(drawer).toBeVisible({ timeout: 10_000 })
  return drawer
}

async function chooseTask(drawer, teacherName) {
  const picker = drawer.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(teacherName)
  const option = picker.getByRole('option').filter({ hasText: teacherName }).first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
  await expect(drawer).toContainText(teacherName)
  await expect(drawer).toContainText(fixture.courseName)
}

function waitForCourseWrite(page, batchId) {
  return page.waitForResponse((response) =>
    response.url().includes(`/academic-affairs/selection/batches/${batchId}/courses`) &&
    response.request().method() === 'POST'
  )
}

test('Academic B W4 formation handoff blocks ADMIN_FIXED and accepts SELECTABLE by real click', async ({ browser }, testInfo) => {
  const batch = await createSelectionBatch(testInfo)
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()

  await loginAcademicAdmin(page)
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
  await dismissGuide(page)
  await selectBatch(page, batch.batchName)

  const drawer = await openAddCourse(page)
  await chooseTask(drawer, fixture.blockedTeacherName)
  await screenshot(page, testInfo, 'w4-formation-admin-fixed-selected-1440x900')

  const blockedWrite = waitForCourseWrite(page, batch.batchId)
  await drawer.getByRole('button', { name: '添加', exact: true }).click()
  const blockedResponse = await blockedWrite
  expect(blockedResponse.ok()).toBeFalsy()
  const blockedBody = await blockedResponse.json()
  expect(String(blockedBody?.message || '')).toContain(fixture.blockedMessage)
  expect(String(blockedResponse.request().postDataJSON()?.teachingTaskId || '')).toBe(fixture.blockedTaskId)
  await expect(drawer).toBeVisible()
  await expect(drawer).toContainText(fixture.blockedMessage)
  await screenshot(page, testInfo, 'w4-formation-admin-fixed-blocked-1440x900')

  await chooseTask(drawer, fixture.selectableTeacherName)
  await expect(drawer).not.toContainText(fixture.blockedMessage)
  const allowedWrite = waitForCourseWrite(page, batch.batchId)
  await drawer.getByRole('button', { name: '添加', exact: true }).click()
  const allowedResponse = await allowedWrite
  expect(allowedResponse.ok(), `selection course add HTTP ${allowedResponse.status()}`).toBeTruthy()
  expect(String(allowedResponse.request().postDataJSON()?.teachingTaskId || '')).toBe(fixture.selectableTaskId)

  await expect(page.getByRole('dialog', { name: '添加可选课程' })).toHaveCount(0, { timeout: 15_000 })
  const row = page.locator('tr').filter({ hasText: fixture.courseName }).filter({ hasText: fixture.selectableTeacherName }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  await screenshot(page, testInfo, 'w4-formation-selectable-persisted-1440x900')

  await page.reload()
  await dismissGuide(page)
  await selectBatch(page, batch.batchName)
  const persisted = page.locator('tr').filter({ hasText: fixture.courseName }).filter({ hasText: fixture.selectableTeacherName }).first()
  await expect(persisted).toBeVisible({ timeout: 20_000 })
  await context.close()
})
