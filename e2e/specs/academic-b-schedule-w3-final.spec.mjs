import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w3-fixture.json'), 'utf8'))

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

async function chooseClassAndLoad(page) {
  const picker = page.locator('.aa-filter .app-remote-select').first()
  await expect(picker).toBeVisible({ timeout: 20_000 })
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(fixture.className)
  const option = picker.getByRole('option').filter({ hasText: fixture.className }).first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
  await page.getByRole('button', { name: '载入课表', exact: true }).click()
  await expect(page.locator('.aa-grid')).toBeVisible({ timeout: 20_000 })
}

async function openEmptyCell(page) {
  const empty = page.locator('.aa-grid__cell.is-editable').filter({ has: page.locator('.aa-grid__add') }).first()
  await expect(empty).toBeVisible({ timeout: 20_000 })
  await empty.click()
  const dialog = page.locator('.app-confirm-dialog')
  await expect(dialog).toBeVisible()
  return dialog
}

async function assertTaskFirstDialog(dialog) {
  const selects = dialog.locator('select.app-select__el')
  await expect(selects.first()).toBeVisible()
  await selects.first().selectOption(fixture.taskId)
  await expect(dialog).toContainText(fixture.courseName)
  await expect(dialog).toContainText(fixture.courseCode)
  await expect(dialog).toContainText(fixture.teacherName)
  await expect(dialog).toContainText(fixture.teacherKey)
  await expect(dialog).toContainText(fixture.className)
  await expect(dialog).toContainText(`${fixture.startWeek}-${fixture.endWeek} 周`)
  await expect(dialog.locator('input[type="number"]')).toHaveCount(2)
  await expect(dialog.getByText('选择教学任务后自动带出')).toHaveCount(0)
}

async function assertPersisted(page) {
  await chooseClassAndLoad(page)
  const item = page.locator('.aa-grid__item').filter({ hasText: fixture.courseName }).first()
  await expect(item).toBeVisible({ timeout: 20_000 })
  await expect(item).toContainText(fixture.teacherName)
  await expect(item).toContainText(`${fixture.startWeek}-${fixture.endWeek}周`)
  return item
}

test('Academic B W3 Task-first schedule real-click + refresh/relogin + File Exchange drawer', async ({ browser }, testInfo) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  await loginAcademicAdmin(page)
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/schedule/${fixture.batchId}/edit`)
  await dismissGuide(page)
  await chooseClassAndLoad(page)

  const dialog = await openEmptyCell(page)
  await assertTaskFirstDialog(dialog)
  await screenshot(page, testInfo, 'w3-task-first-selected-1440x900')

  const write = page.waitForResponse((response) =>
    response.url().includes(`/academic-affairs/schedule-batches/${fixture.batchId}/items`) &&
    response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '确认排课', exact: true }).click()
  const response = await write
  expect(response.ok(), `schedule add HTTP ${response.status()}`).toBeTruthy()
  const requestBody = response.request().postDataJSON()
  expect(String(requestBody?.taskId || '')).toBe(fixture.taskId)
  expect(requestBody?.courseName).toBeUndefined()
  expect(requestBody?.teacherName).toBeUndefined()
  expect(requestBody?.className).toBeUndefined()

  await expect(page.locator('.app-confirm-dialog')).toHaveCount(0, { timeout: 15_000 })
  await assertPersisted(page)
  await screenshot(page, testInfo, 'w3-scheduled-success-1440x900')

  await page.reload()
  await dismissGuide(page)
  await assertPersisted(page)
  await context.close()

  const reloginContext = await browser.newContext({ viewport: { width: 1280, height: 720 } })
  const relogin = await reloginContext.newPage()
  await loginAcademicAdmin(relogin)
  await relogin.goto(`${config.staffBaseUrl}/admin/academic-affairs/schedule/${fixture.batchId}/edit`)
  await dismissGuide(relogin)
  await assertPersisted(relogin)
  await screenshot(relogin, testInfo, 'w3-relogin-persisted-1280x720')

  await relogin.getByRole('button', { name: '批量导入 XLSX', exact: true }).click()
  await expect(relogin.getByText('批量导入课表', { exact: true })).toBeVisible()
  await expect(relogin.getByText('排课结果导入模板.xlsx', { exact: true })).toBeVisible()
  await expect(relogin.locator('textarea')).toHaveCount(0)
  await screenshot(relogin, testInfo, 'w3-file-exchange-drawer-1280x720')
  await reloginContext.close()
})
