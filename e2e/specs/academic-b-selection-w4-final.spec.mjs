import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w4-fixture.json'), 'utf8'))

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
    batchName: `B-W4-Task身份闭环-${suffix}`,
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
  await expect(drawer.getByText('课程', { exact: true })).toHaveCount(0)
  const taskPicker = drawer.getByRole('combobox').first()
  await expect(taskPicker).toBeVisible()
  await expect(taskPicker).toContainText('选择当前批次学期的 READY 教学任务')
  return drawer
}

async function chooseTask(drawer) {
  const picker = drawer.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(fixture.courseCode)
  const option = picker.getByRole('option').filter({ hasText: fixture.courseName }).first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
  await expect(drawer).toContainText(fixture.courseCode)
  await expect(drawer).toContainText(fixture.courseName)
  await expect(drawer).toContainText(fixture.teacherName)
  await expect(drawer).toContainText(fixture.className)
  await expect(drawer).toContainText('提交时不允许手工改写')
}

async function assertPersisted(page, batchName) {
  await selectBatch(page, batchName)
  const row = page.locator('tr').filter({ hasText: fixture.courseName }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  await expect(row).toContainText(fixture.teacherName)
  return row
}

test('Academic B W4 TeachingTask-first selection supply real-click + refresh/relogin', async ({ browser }, testInfo) => {
  const batch = await createSelectionBatch(testInfo)

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  await loginAcademicAdmin(page)
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
  await dismissGuide(page)
  await selectBatch(page, batch.batchName)

  const drawer = await openAddCourse(page)
  await screenshot(page, testInfo, 'w4-task-first-empty-1440x900')
  await chooseTask(drawer)
  await screenshot(page, testInfo, 'w4-task-selected-readonly-1440x900')

  const write = page.waitForResponse((response) =>
    response.url().includes(`/academic-affairs/selection/batches/${batch.batchId}/courses`) &&
    response.request().method() === 'POST'
  )
  await drawer.getByRole('button', { name: '添加', exact: true }).click()
  const response = await write
  expect(response.ok(), `selection course add HTTP ${response.status()}`).toBeTruthy()
  const requestBody = response.request().postDataJSON()
  expect(String(requestBody?.teachingTaskId || '')).toBe(fixture.taskId)
  expect(String(requestBody?.courseId || '')).toBe(fixture.courseId)
  expect(requestBody?.teacherName).toBeUndefined()
  expect(requestBody?.courseName).toBeUndefined()
  expect(requestBody?.teachingClassName).toBeUndefined()

  await expect(page.getByRole('dialog', { name: '添加可选课程' })).toHaveCount(0, { timeout: 15_000 })
  await assertPersisted(page, batch.batchName)
  await screenshot(page, testInfo, 'w4-course-added-1440x900')

  await page.reload()
  await dismissGuide(page)
  await assertPersisted(page, batch.batchName)
  await context.close()

  const reloginContext = await browser.newContext({ viewport: { width: 1280, height: 720 } })
  const relogin = await reloginContext.newPage()
  await loginAcademicAdmin(relogin)
  await relogin.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
  await dismissGuide(relogin)
  const reloginRow = await assertPersisted(relogin, batch.batchName)
  await reloginRow.scrollIntoViewIfNeeded()
  await screenshot(relogin, testInfo, 'w4-relogin-persisted-1280x720')
  await reloginContext.close()
})
