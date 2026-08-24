import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w5-fixture.json'), 'utf8'))

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

async function addTaskCourse(page, batchId, courseFact) {
  await page.getByRole('button', { name: '+ 添加课程', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '添加可选课程' })
  await expect(drawer).toBeVisible({ timeout: 10_000 })
  const picker = drawer.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(courseFact.teacherName)
  const option = picker.getByRole('option')
    .filter({ hasText: courseFact.teacherName })
    .filter({ hasText: courseFact.courseName })
    .first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
  await expect(drawer).toContainText(courseFact.courseName)
  await expect(drawer).toContainText(courseFact.teacherName)
  const write = page.waitForResponse((response) =>
    response.url().includes(`/academic-affairs/selection/batches/${batchId}/courses`) &&
    response.request().method() === 'POST'
  )
  await drawer.getByRole('button', { name: '添加', exact: true }).click()
  const response = await write
  expect(response.ok(), `add selection course HTTP ${response.status()}`).toBeTruthy()
  return (await response.json()).data
}

async function lifecycle(page, batchId, buttonName, endpointSuffix) {
  await page.getByRole('button', { name: buttonName, exact: true }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: buttonName }).last()
  await expect(dialog).toBeVisible({ timeout: 10_000 })
  const write = page.waitForResponse((response) =>
    response.url().includes(`/academic-affairs/selection/batches/${batchId}/${endpointSuffix}`) &&
    response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  const response = await write
  expect(response.ok(), `${buttonName} HTTP ${response.status()}`).toBeTruthy()
  return (await response.json()).data
}

test('AA-011 Staff PC real-click creates term-bound batch, adds supply, publishes and opens', async ({ browser }, testInfo) => {
  const pcCourse = fixture.courses.find((row) => row.role === 'PC')
  const miniCourse = fixture.courses.find((row) => row.role === 'MINIAPP')
  expect(pcCourse).toBeTruthy()
  expect(miniCourse).toBeTruthy()

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  await loginAcademicAdmin(page)
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
  await dismissGuide(page)

  const suffix = `${String(Date.now()).slice(-8)}-r${testInfo.retry}`
  const batchName = `AA-011真实页面选课-${suffix}`
  await page.getByRole('button', { name: '新建批次', exact: true }).click()
  const create = page.getByRole('dialog', { name: '新建选课批次' })
  await expect(create).toBeVisible({ timeout: 10_000 })
  await create.getByRole('textbox').first().fill(batchName)

  const createdWrite = page.waitForResponse((response) =>
    response.url().includes('/academic-affairs/selection/batches') &&
    !response.url().includes('/courses') &&
    response.request().method() === 'POST'
  )
  await create.getByRole('button', { name: '创建', exact: true }).click()
  const createdResponse = await createdWrite
  expect(createdResponse.ok(), `create selection batch HTTP ${createdResponse.status()}`).toBeTruthy()
  const created = (await createdResponse.json()).data
  expect(String(created.termId || ''), 'Staff PC-created batch must bind the authoritative term').toBe(String(fixture.termId))
  await selectBatch(page, batchName)

  const pcSupply = await addTaskCourse(page, created.batchId, pcCourse)
  const miniSupply = await addTaskCourse(page, created.batchId, miniCourse)
  expect(String(pcSupply.teachingTaskId || '')).toBe(String(pcCourse.taskId))
  expect(String(miniSupply.teachingTaskId || '')).toBe(String(miniCourse.taskId))

  const published = await lifecycle(page, created.batchId, '发布', 'publish')
  expect(published.status).toBe('PUBLISHED')
  const opened = await lifecycle(page, created.batchId, '开选', 'open')
  expect(opened.status).toBe('OPEN')

  await page.reload()
  await dismissGuide(page)
  await selectBatch(page, batchName)
  await expect(page.locator('.aasel-detail')).toContainText('正在选课')
  await expect(page.locator('tr').filter({ hasText: pcCourse.courseName }).first()).toContainText(pcCourse.teacherName)
  await expect(page.locator('tr').filter({ hasText: miniCourse.courseName }).first()).toContainText(miniCourse.teacherName)

  fs.writeFileSync(path.resolve(here, '../academic-aa011-staff-browser-fixture.json'), JSON.stringify({
    batchId: String(created.batchId),
    batchName,
    termId: String(created.termId),
    pcSelectionCourseId: String(pcSupply.selectionCourseId),
    miniSelectionCourseId: String(miniSupply.selectionCourseId),
  }, null, 2))
  await context.close()
})
