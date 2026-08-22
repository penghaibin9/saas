import { readFileSync } from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const fixture = JSON.parse(readFileSync(
  new URL('../academic-exam-incident-w2-fixture.json', import.meta.url),
  'utf8'
))
const account = {
  tenant: fixture.tenant,
  username: fixture.username,
  password: fixture.password
}

function waitForBrowserRefresh(page, timeout = 20_000) {
  return page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') &&
      response.request().method() === 'POST' && response.status() === 200,
    { timeout }
  )
}

async function dismissGuide(page) {
  const guide = page.getByRole('dialog', { name: '页面操作引导' })
  if (!(await guide.isVisible({ timeout: 1_000 }).catch(() => false))) return
  const skip = guide.getByRole('button', { name: '跳过引导' })
  if (await skip.isVisible({ timeout: 1_000 }).catch(() => false)) await skip.click()
}

async function openExamConsole(page) {
  const refresh = waitForBrowserRefresh(page)
  await page.goto(new URL('/admin/academic-affairs/exam', config.staffBaseUrl).toString())
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissGuide(page)
  const batch = page.locator('.aaexam-batch').filter({ hasText: fixture.batchName }).first()
  await expect(batch).toBeVisible({ timeout: 20_000 })
  await batch.click()
  await expect(page.getByText('异常处置', { exact: true })).toBeVisible({ timeout: 20_000 })
}

async function filterToStudent(page, studentNo) {
  const request = page.waitForResponse(
    (response) => response.url().includes('/api/v1/academic-affairs/exam/incidents/workbench') &&
      response.url().includes(`keyword=${encodeURIComponent(studentNo)}`) &&
      response.request().method() === 'GET',
    { timeout: 20_000 }
  )
  await page.getByLabel('学生 / 课程 / 考场').fill(studentNo)
  await page.getByRole('button', { name: '查询' }).click()
  const response = await request
  expect(response.status()).toBe(200)
  const row = page.getByRole('row').filter({ hasText: studentNo }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  return row
}

async function openDetail(page, studentNo) {
  const row = await filterToStudent(page, studentNo)
  await row.getByRole('button', { name: '详情 / 处置' }).click()
  await expect(page.getByText('考场异常详情 / 正式处置', { exact: true })).toBeVisible()
}

async function confirmDecision(page, title, confirmText, reason, incidentId) {
  const dialog = page.getByRole('dialog').filter({ hasText: title }).first()
  await expect(dialog).toBeVisible()
  const reasonBox = dialog.getByRole('textbox')
  await reasonBox.fill(reason)
  const resolvePromise = page.waitForResponse(
    (response) => response.url().includes(`/api/v1/academic-affairs/exam/incidents/${incidentId}/resolve`) &&
      response.request().method() === 'POST',
    { timeout: 20_000 }
  )
  const reloadPromise = page.waitForResponse(
    (response) => response.url().includes('/api/v1/academic-affairs/exam/incidents/workbench') &&
      response.request().method() === 'GET',
    { timeout: 20_000 }
  )
  await dialog.getByRole('button', { name: confirmText }).click()
  const resolve = await resolvePromise
  expect(resolve.status()).toBe(200)
  const payload = await resolve.json()
  expect(payload.code).toBe(0)
  await reloadPromise
  return payload.data
}

async function capture(page, testInfo, name) {
  const path = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path, contentType: 'image/png' })
}

test('W2 exam incidents: OPEN -> CLOSE / HANDOFF / VOID with server-authoritative history', async ({ page }, testInfo) => {
  const attempt = fixture.attempts[Math.min(testInfo.retry, fixture.attempts.length - 1)]
  const api = await loginApi(account)
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  await openExamConsole(page)

  // Risk delivery is evidence only; it must still appear OPEN before an explicit CLOSE.
  await openDetail(page, attempt.absent.studentNo)
  await expect(page.getByText('风险通知已送达，但这不等于考务正式关闭', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '确认关闭' }).click()
  const closed = await confirmDecision(
    page,
    '确认正式关闭缺考异常',
    '确认关闭',
    `W2浏览器验收：缺考风险已送达辅导员，正式关闭 ${testInfo.retry}`,
    attempt.absent.incidentId
  )
  expect(closed.closureStatus).toBe('RISK_TRANSFERRED')
  const closeTruth = await api.get(`/academic-affairs/exam/incidents/workbench?batchId=${fixture.batchId}&keyword=${attempt.absent.studentNo}&view=ALL&page=1&pageSize=20`)
  expect(closeTruth.items).toHaveLength(1)
  expect(closeTruth.items[0].closureStatus).toBe('RISK_TRANSFERRED')
  expect(closeTruth.items[0].resolutionAction).toBe('CLOSE')
  await capture(page, testInfo, 'w2-absent-formally-closed')

  // Discipline violation is handed to the existing student-affairs owner by stable reference only.
  await page.getByRole('button', { name: '清空' }).click()
  await openDetail(page, attempt.discipline.studentNo)
  const caseRef = `DISC-W2-E2E-${process.env.GITHUB_RUN_ID || 'LOCAL'}-${testInfo.retry}`
  await page.getByLabel('处分 / 后续处理线索编号（HANDOFF 必填）').fill(caseRef)
  await page.getByRole('button', { name: '移交处理线索' }).click()
  const handed = await confirmDecision(
    page,
    '确认移交异常线索',
    '确认移交',
    `W2浏览器验收：违纪事实核验完成，移交学工处分流程 ${testInfo.retry}`,
    attempt.discipline.incidentId
  )
  expect(handed.closureStatus).toBe('CASE_LINKED')
  expect(handed.disciplineCaseRef).toBe(caseRef)
  const handoffTruth = await api.get(`/academic-affairs/exam/incidents/workbench?batchId=${fixture.batchId}&keyword=${attempt.discipline.studentNo}&view=ALL&page=1&pageSize=20`)
  expect(handoffTruth.items[0].closureStatus).toBe('CASE_LINKED')
  expect(handoffTruth.items[0].disciplineCaseRef).toBe(caseRef)
  expect(handoffTruth.items[0].resolutionAction).toBe('HANDOFF')
  await capture(page, testInfo, 'w2-discipline-handed-off')

  // Wrong occurrence is voided but never deleted; history remains queryable.
  await page.getByRole('button', { name: '清空' }).click()
  await openDetail(page, attempt.void.studentNo)
  await page.getByRole('button', { name: '作废误登记' }).click()
  const voided = await confirmDecision(
    page,
    '确认作废异常登记',
    '确认作废',
    `W2浏览器验收：监考误选学生，复核确认保留历史后作废 ${testInfo.retry}`,
    attempt.void.incidentId
  )
  expect(voided.closureStatus).toBe('VOIDED')
  const voidTruth = await api.get(`/academic-affairs/exam/incidents/workbench?batchId=${fixture.batchId}&keyword=${attempt.void.studentNo}&view=VOIDED&page=1&pageSize=20`)
  expect(voidTruth.items).toHaveLength(1)
  expect(voidTruth.items[0].closureStatus).toBe('VOIDED')
  expect(voidTruth.items[0].resolutionAction).toBe('VOID')
  await capture(page, testInfo, 'w2-misrecord-voided-history-preserved')

  // Terminal event is immutable: a competing action after CLOSE cannot overwrite it.
  const replay = await api.post(`/academic-affairs/exam/incidents/${attempt.absent.incidentId}/resolve`, {
    action: 'VOID',
    reason: '浏览器验收尝试覆盖已关闭事实，应由状态机拒绝'
  }).catch((error) => error)
  const replayStatus = replay?.status || replay?.response?.status || replay?.statusCode
  if (replayStatus != null) expect(Number(replayStatus)).toBe(409)

  const finalTruth = await api.get(`/academic-affairs/exam/incidents/workbench?batchId=${fixture.batchId}&view=ALL&page=1&pageSize=100`)
  const byId = new Map(finalTruth.items.map((row) => [row.incidentId, row]))
  expect(byId.get(attempt.absent.incidentId).resolutionAction).toBe('CLOSE')
  expect(byId.get(attempt.discipline.incidentId).resolutionAction).toBe('HANDOFF')
  expect(byId.get(attempt.void.incidentId).resolutionAction).toBe('VOID')
})
