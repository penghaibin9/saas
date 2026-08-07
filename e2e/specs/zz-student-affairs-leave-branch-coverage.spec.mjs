import { execFileSync } from 'node:child_process'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadStudentAffairsFixture } from '../lib/student-affairs-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import {
  StaffStudentAffairsLeavePage,
  StudentAffairsPortalPage
} from '../pages/student-affairs.page.mjs'

function localDate(daysFromToday = 0) {
  const date = new Date()
  date.setDate(date.getDate() + daysFromToday)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function expectBusinessSuccess(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} returned HTTP ${response.status()}: ${text.slice(0, 1000)}`).toBeTruthy()
  if (body && Object.prototype.hasOwnProperty.call(body, 'code')) {
    expect(body.code, `${action} returned business error: ${text.slice(0, 1000)}`).toBe(0)
  }
  return body
}

async function expectBusinessDenied(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  const businessOk = response.ok()
    && (!body || !Object.prototype.hasOwnProperty.call(body, 'code') || body.code === 0)
  expect(businessOk, `${action} unexpectedly succeeded: HTTP ${response.status()} ${text.slice(0, 1000)}`).toBeFalsy()
  expect(
    `${text} ${JSON.stringify(body || {})}`,
    `${action} should fail because of data scope/permission, not an unrelated validation error`
  ).toMatch(/NO_DATA_SCOPE|NO_PERMISSION|403002|数据范围|无权|不在您的管理范围/)
  return body
}

async function browserLocalNow(page) {
  return page.evaluate(() => {
    const d = new Date()
    const p = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
  })
}

function backdateApprovedLeave(leaveId, daysBack = 2) {
  const output = execFileSync(
    process.env.PYTHON || 'python',
    ['../backend/scripts/e2e_backdate_student_affairs_leave.py', String(leaveId), '--days-back', String(daysBack)],
    { cwd: process.cwd(), env: process.env, encoding: 'utf8' }
  )
  const lines = String(output || '').trim().split(/\r?\n/).filter(Boolean)
  const payload = JSON.parse(lines.at(-1) || '{}')
  expect(String(payload.leaveId || '')).toBe(String(leaveId))
  expect(payload.status).toBe('APPROVED')
  return payload
}

async function loginStudentC(page) {
  const login = new StudentLoginPage(page, config.studentBaseUrl)
  await login.login(config.studentC)
  return new StudentAffairsPortalPage(page, config.studentBaseUrl, {})
}

async function loginOutsideStudent(page) {
  const login = new StudentLoginPage(page, config.studentBaseUrl)
  await login.login(config.outsideStudent)
  return new StudentAffairsPortalPage(page, config.studentBaseUrl, {})
}

async function loginMentor(page, fixture) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.mentor)
  await login.switchRole(/辅导员|COUNSELOR/)
  return {
    login,
    affairs: new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
  }
}

async function loginAdmin(page, fixture) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.sandboxAdmin)
  return {
    login,
    affairs: new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
  }
}

async function studentRecord(page, startDate, endDate = startDate) {
  let rows = page.locator('article.record').filter({ hasText: startDate })
  if (endDate !== startDate) rows = rows.filter({ hasText: endDate })
  await expect(rows.first(), `未找到学生端请假记录 ${startDate} ~ ${endDate}`).toBeVisible()
  return rows.first()
}

async function submitStudentLeave(page, { startDate, endDate, reason, outside = false }) {
  const affairs = outside ? await loginOutsideStudent(page) : await loginStudentC(page)
  const leaveId = await affairs.submitLeave({ startDate, endDate, reason })
  expect(leaveId).not.toBe('')
  return leaveId
}

async function approvalAction(page, fixture, {
  leaveId,
  account = 'mentor',
  before,
  button,
  confirm,
  endpoint,
  after,
  reason = ''
}) {
  const session = account === 'admin' ? await loginAdmin(page, fixture) : await loginMentor(page, fixture)
  await session.affairs.openApproval()
  const { data } = await session.affairs.clickExactQueueLeave(leaveId, `打开待处理请假 ${leaveId}`)
  expect(data.affairsStatus).toBe(before)

  const action = page.locator('.lv-foot').getByRole('button', { name: button })
  await expect(action).toBeEnabled()
  await action.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  if (reason) await dialog.locator('textarea').fill(reason)

  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/${endpoint}`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: confirm }).click()
  const body = await expectBusinessSuccess(await responsePromise, `${button} ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe(after)
  return body?.data || {}
}

async function approveOneDay(page, fixture, leaveId) {
  return approvalAction(page, fixture, {
    leaveId,
    before: 'COUNSELOR_REVIEW',
    button: '通过',
    confirm: '通过',
    endpoint: 'approve',
    after: 'APPROVED'
  })
}

async function openFollowup(page, affairs, status) {
  await page.goto(`${config.staffBaseUrl.replace(/\/+$/, '')}/admin/student-affairs/leave/followup?status=${encodeURIComponent(status)}`)
  await expect(page.getByText('延期销假').first()).toBeVisible()
  await affairs.dismissGuideIfPresent()
}

async function studentSubmitCancel(page, leaveId, startDate, endDate = startDate) {
  const affairs = await loginStudentC(page)
  await affairs.openLeave()
  const record = await studentRecord(page, startDate, endDate)
  const button = record.getByRole('button', { name: '申请销假' })
  await expect(button).toBeEnabled()
  page.once('dialog', async (dialog) => {
    expect(dialog.type()).toBe('confirm')
    await dialog.accept()
  })
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/portal/affairs/leave/${leaveId}/cancel`
      && response.request().method() === 'POST'
  )
  await button.click()
  const body = await expectBusinessSuccess(await responsePromise, `学生申请销假 ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe('WAIT_CANCEL_LEAVE')
}

async function studentSubmitExtension(page, leaveId, startDate, endDate, newEndDate, reason) {
  const affairs = await loginStudentC(page)
  await affairs.openLeave()
  const record = await studentRecord(page, startDate, endDate)
  const button = record.getByRole('button', { name: '申请续假' })
  await expect(button).toBeEnabled()
  await button.click()
  const form = record.locator('.inline-form')
  await expect(form).toBeVisible()
  await form.locator('input[type="date"]').fill(newEndDate)
  await form.locator('textarea').fill(reason)
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/portal/affairs/leave/${leaveId}/extension`
      && response.request().method() === 'POST'
  )
  await form.getByRole('button', { name: '提交续假' }).click()
  const body = await expectBusinessSuccess(await responsePromise, `学生提交续假 ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe('EXTENSION_REVIEW')
  return body?.data || {}
}

async function counselorConfirmCancel(page, fixture, leaveId) {
  const { affairs } = await loginMentor(page, fixture)
  await affairs.confirmCancel(leaveId)
}

async function returnCancel(page, fixture, leaveId, reason) {
  const { affairs } = await loginMentor(page, fixture)
  await openFollowup(page, affairs, 'WAIT_CANCEL_LEAVE')
  const { data } = await affairs.clickExactQueueLeave(leaveId, '打开待销假退回记录')
  expect(data.affairsStatus).toBe('WAIT_CANCEL_LEAVE')
  const button = page.locator('.lv-foot').getByRole('button', { name: '销假退回' })
  await expect(button).toBeEnabled()
  await button.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.locator('textarea').fill(reason)
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/cancel-confirm`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '退回重办' }).click()
  const body = await expectBusinessSuccess(await responsePromise, `辅导员销假退回 ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe('APPROVED')
  return body?.data || {}
}

async function rejectExtension(page, fixture, leaveId, oldEndDate, reason) {
  const { affairs } = await loginMentor(page, fixture)
  await openFollowup(page, affairs, 'EXTENSION_REVIEW')
  const { data } = await affairs.clickExactQueueLeave(leaveId, '打开待续假驳回记录')
  expect(data.affairsStatus).toBe('EXTENSION_REVIEW')
  const submitted = (data.extensions || []).find((row) => row.status === 'SUBMITTED')
  expect(submitted, '续假审批前必须存在 SUBMITTED 续假记录').toBeTruthy()

  const button = page.locator('.lv-foot').getByRole('button', { name: '续假驳回' })
  await expect(button).toBeEnabled()
  await button.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.locator('textarea').fill(reason)
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/extension-approve`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '驳回续假' }).click()
  const body = await expectBusinessSuccess(await responsePromise, `辅导员续假驳回 ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe('APPROVED')
  expect(String(body?.data?.endTime || '')).toContain(oldEndDate)
  return body?.data || {}
}

async function approveExtension(page, fixture, leaveId, expectedEndDate) {
  const { affairs } = await loginMentor(page, fixture)
  await openFollowup(page, affairs, 'EXTENSION_REVIEW')
  const { data } = await affairs.clickExactQueueLeave(leaveId, '打开待续假通过记录')
  expect(data.affairsStatus).toBe('EXTENSION_REVIEW')
  const button = page.locator('.lv-foot').getByRole('button', { name: '续假通过' })
  await expect(button).toBeEnabled()
  await button.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/extension-approve`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '通过续假' }).click()
  const body = await expectBusinessSuccess(await responsePromise, `辅导员续假通过 ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe('APPROVED')
  expect(String(body?.data?.endTime || '')).toContain(expectedEndDate)
  return body?.data || {}
}

async function fillDateTimeDrawer(drawer, value) {
  const input = drawer.locator('.el-input__inner').first()
  await expect(input).toBeVisible()
  await input.click()
  await input.fill(value.replace('T', ' '))
  await input.press('Enter')
  await expect(input).not.toHaveValue('')
}

async function proxyCancel(page, fixture, leaveId, status, buttonLabel, note) {
  const { affairs } = await loginMentor(page, fixture)
  await openFollowup(page, affairs, status)
  const { data } = await affairs.clickExactQueueLeave(leaveId, `打开${buttonLabel}记录`)
  expect(data.affairsStatus).toBe(status)

  const button = page.locator('.lv-foot').getByRole('button', { name: buttonLabel })
  await expect(button).toBeEnabled()
  await button.click()
  const drawer = page.getByRole('dialog', { name: '代登记销假' })
  await expect(drawer).toBeVisible()
  await fillDateTimeDrawer(drawer, await browserLocalNow(page))
  await drawer.locator('textarea').fill(note)

  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/proxy-cancel`
      && response.request().method() === 'POST'
  )
  await drawer.getByRole('button', { name: '代登记销假' }).click()
  const body = await expectBusinessSuccess(await responsePromise, `${buttonLabel} ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe('WAIT_CANCEL_LEAVE')
  return body?.data || {}
}

async function overdueHandle(page, fixture, leaveId, handleType, expectedStatus, note) {
  const { affairs } = await loginMentor(page, fixture)
  await openFollowup(page, affairs, 'OVERDUE')
  const { data } = await affairs.clickExactQueueLeave(leaveId, `打开逾期处置 ${handleType}`)
  expect(data.affairsStatus).toBe('OVERDUE')
  const button = page.locator('.lv-foot').getByRole('button', { name: '逾期处置' })
  await expect(button).toBeEnabled()
  await button.click()
  const drawer = page.getByRole('dialog', { name: '逾期处置' })
  await expect(drawer).toBeVisible()
  await drawer.locator('select.app-select__el').selectOption(handleType)
  await drawer.locator('textarea').fill(note)
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/student-affairs/leave/${leaveId}/overdue-handle`
      && response.request().method() === 'POST'
  )
  await drawer.getByRole('button', { name: '登记处置' }).click()
  const body = await expectBusinessSuccess(await responsePromise, `逾期处置 ${handleType} ${leaveId}`)
  expect(body?.data?.affairsStatus).toBe(expectedStatus)
  return body?.data || {}
}

test.describe('学工请假遗漏业务分支真实点击覆盖', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let runId

  let directOutsideLeaveId = ''
  let rejectedLeaveId = ''
  let cancelReturnLeaveId = ''
  let extensionRejectLeaveId = ''
  let staffExtensionLeaveId = ''
  let proxyCancelLeaveId = ''
  let overdueCloseLeaveId = ''
  let overdueProxyLeaveId = ''
  let mediumLeaveId = ''
  let majorLeaveId = ''

  const dates = {
    rejected: [localDate(10), localDate(10)],
    cancelReturn: [localDate(12), localDate(12)],
    extensionReject: [localDate(14), localDate(14), localDate(15)],
    staffExtension: [localDate(17), localDate(17), localDate(18)],
    proxyCancel: [localDate(20), localDate(20)],
    overdueClose: [localDate(22), localDate(22)],
    overdueProxy: [localDate(24), localDate(24)],
    medium: [localDate(27), localDate(31)],
    major: [localDate(34), localDate(42)],
    outside: [localDate(45), localDate(45)]
  }

  test.beforeAll(async () => {
    fixture = await loadStudentAffairsFixture()
    runId = String(process.env.GITHUB_RUN_ID || Date.now()).replace(/\D/g, '').slice(-12)
  })

  test('其他行政班学生再创建真实样本，辅导员拿到 leaveId 也不能直接详情/审批/退回', async ({ page }) => {
    directOutsideLeaveId = await submitStudentLeave(page, {
      startDate: dates.outside[0],
      endDate: dates.outside[1],
      reason: `跨班直接对象越权验证 ${runId}`,
      outside: true
    })

    const { login } = await loginMentor(page, fixture)
    const token = await login.token()
    const headers = { Authorization: `Bearer ${token}` }

    const detail = await page.request.get(`${config.apiBaseUrl}/student-affairs/leave/${directOutsideLeaveId}`, { headers })
    await expectBusinessDenied(detail, '跨班直接读取请假详情')

    const approve = await page.request.post(`${config.apiBaseUrl}/student-affairs/leave/${directOutsideLeaveId}/approve`, {
      headers,
      data: { comment: '越权审批不应成功', version: 0 }
    })
    await expectBusinessDenied(approve, '跨班直接审批请假')

    const returned = await page.request.post(`${config.apiBaseUrl}/student-affairs/leave/${directOutsideLeaveId}/return`, {
      headers,
      data: { reason: '跨班退回不应成功', version: 0 }
    })
    await expectBusinessDenied(returned, '跨班直接退回请假')
  })

  test('辅导员真实点击终态驳回，学生只能看到驳回结果且不能修改重提', async ({ page }) => {
    rejectedLeaveId = await submitStudentLeave(page, {
      startDate: dates.rejected[0],
      endDate: dates.rejected[1],
      reason: `终态驳回点击验证 ${runId}`
    })
  })

  test('辅导员点击驳回并填写原因后写入 REJECTED 终态', async ({ page }) => {
    const reason = `材料事实不足，终态驳回 ${runId}`
    const data = await approvalAction(page, fixture, {
      leaveId: rejectedLeaveId,
      before: 'COUNSELOR_REVIEW',
      button: '驳回',
      confirm: '驳回',
      endpoint: 'reject',
      after: 'REJECTED',
      reason
    })
    expect(data.returnReason).toBe(reason)
  })

  test('学生 PC 对 REJECTED 记录不出现修改重提/销假/续假入口', async ({ page }) => {
    const affairs = await loginStudentC(page)
    await affairs.openLeave()
    const record = await studentRecord(page, dates.rejected[0])
    await expect(record).toContainText(/已驳回|REJECTED/)
    await expect(record.getByRole('button', { name: '修改后重提' })).toHaveCount(0)
    await expect(record.getByRole('button', { name: '申请销假' })).toHaveCount(0)
    await expect(record.getByRole('button', { name: '申请续假' })).toHaveCount(0)
  })

  test('学生创建销假退回样本并由辅导员审批通过', async ({ page }) => {
    cancelReturnLeaveId = await submitStudentLeave(page, {
      startDate: dates.cancelReturn[0],
      endDate: dates.cancelReturn[1],
      reason: `销假退回重办点击验证 ${runId}`
    })
  })

  test('辅导员通过销假退回样本', async ({ page }) => {
    await approveOneDay(page, fixture, cancelReturnLeaveId)
  })

  test('学生第一次点击申请销假进入 WAIT_CANCEL_LEAVE', async ({ page }) => {
    await studentSubmitCancel(page, cancelReturnLeaveId, dates.cancelReturn[0])
  })

  test('辅导员点击销假退回后，请假恢复 APPROVED', async ({ page }) => {
    await returnCancel(page, fixture, cancelReturnLeaveId, `返校证明需补充后重新销假 ${runId}`)
  })

  test('学生看到销假入口恢复并第二次真实提交销假', async ({ page }) => {
    const affairs = await loginStudentC(page)
    await affairs.openLeave()
    const record = await studentRecord(page, dates.cancelReturn[0])
    await expect(record).toContainText(/已通过|APPROVED/)
    await expect(record.getByRole('button', { name: '申请销假' })).toBeEnabled()
    await studentSubmitCancel(page, cancelReturnLeaveId, dates.cancelReturn[0])
  })

  test('辅导员确认第二次销假，退回重办链最终 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, cancelReturnLeaveId)
  })

  test('学生创建续假驳回样本并由辅导员审批通过', async ({ page }) => {
    extensionRejectLeaveId = await submitStudentLeave(page, {
      startDate: dates.extensionReject[0],
      endDate: dates.extensionReject[1],
      reason: `续假驳回点击验证 ${runId}`
    })
  })

  test('辅导员通过续假驳回样本', async ({ page }) => {
    await approveOneDay(page, fixture, extensionRejectLeaveId)
  })

  test('学生点击申请续假进入 EXTENSION_REVIEW', async ({ page }) => {
    await studentSubmitExtension(
      page,
      extensionRejectLeaveId,
      dates.extensionReject[0],
      dates.extensionReject[1],
      dates.extensionReject[2],
      `续假驳回前的真实申请 ${runId}`
    )
  })

  test('辅导员点击续假驳回，原结束日期保持不变', async ({ page }) => {
    await rejectExtension(
      page,
      fixture,
      extensionRejectLeaveId,
      dates.extensionReject[1],
      `续假依据不足，维持原日期 ${runId}`
    )
  })

  test('学生看到原日期和 APPROVED，之后销假关闭该样本', async ({ page }) => {
    const affairs = await loginStudentC(page)
    await affairs.openLeave()
    const record = await studentRecord(page, dates.extensionReject[0], dates.extensionReject[1])
    await expect(record).toContainText(/已通过|APPROVED/)
    await expect(record).toContainText(dates.extensionReject[1])
    await expect(record.getByRole('button', { name: '申请续假' })).toBeEnabled()
    await studentSubmitCancel(page, extensionRejectLeaveId, dates.extensionReject[0], dates.extensionReject[1])
  })

  test('辅导员确认续假驳回样本销假为 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, extensionRejectLeaveId)
  })

  test('学生创建老师代发起续假样本并审批通过', async ({ page }) => {
    staffExtensionLeaveId = await submitStudentLeave(page, {
      startDate: dates.staffExtension[0],
      endDate: dates.staffExtension[1],
      reason: `老师代发起续假点击验证 ${runId}`
    })
  })

  test('辅导员通过老师代发起续假样本', async ({ page }) => {
    await approveOneDay(page, fixture, staffExtensionLeaveId)
  })

  test('辅导员在延期销假页点击发起续假并填写新结束时间', async ({ page }) => {
    const { affairs } = await loginMentor(page, fixture)
    await openFollowup(page, affairs, 'APPROVED')
    const { data } = await affairs.clickExactQueueLeave(staffExtensionLeaveId, '打开老师代发起续假样本')
    expect(data.affairsStatus).toBe('APPROVED')

    const action = page.locator('.lv-foot').getByRole('button', { name: '发起续假' })
    await expect(action).toBeEnabled()
    await action.click()
    const drawer = page.getByRole('dialog', { name: '发起续假' })
    await expect(drawer).toBeVisible()
    await fillDateTimeDrawer(drawer, `${dates.staffExtension[2]}T12:00`)
    await drawer.locator('textarea').fill(`辅导员代学生发起续假并留痕 ${runId}`)

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/student-affairs/leave/${staffExtensionLeaveId}/extension`
        && response.request().method() === 'POST'
    )
    await drawer.getByRole('button', { name: '提交续假' }).click()
    const body = await expectBusinessSuccess(await responsePromise, '辅导员代发起续假')
    expect(body?.data?.affairsStatus).toBe('EXTENSION_REVIEW')
  })

  test('辅导员点击续假通过后新结束时间写回', async ({ page }) => {
    await approveExtension(page, fixture, staffExtensionLeaveId, dates.staffExtension[2])
  })

  test('学生销假关闭老师代发起续假样本', async ({ page }) => {
    await studentSubmitCancel(page, staffExtensionLeaveId, dates.staffExtension[0], dates.staffExtension[2])
  })

  test('辅导员确认老师代发起续假样本销假为 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, staffExtensionLeaveId)
  })

  test('学生创建代登记销假样本并由辅导员审批通过', async ({ page }) => {
    proxyCancelLeaveId = await submitStudentLeave(page, {
      startDate: dates.proxyCancel[0],
      endDate: dates.proxyCancel[1],
      reason: `辅导员代登记销假点击验证 ${runId}`
    })
  })

  test('辅导员通过代登记销假样本并仅将时间前置到已返校', async ({ page }) => {
    await approveOneDay(page, fixture, proxyCancelLeaveId)
    backdateApprovedLeave(proxyCancelLeaveId, 2)
  })

  test('辅导员真实点击代登记销假并选择当前本地时间', async ({ page }) => {
    await proxyCancel(page, fixture, proxyCancelLeaveId, 'APPROVED', '代登记销假', `本人已返校，辅导员代登记 ${runId}`)
  })

  test('辅导员确认代登记销假样本为 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, proxyCancelLeaveId)
  })

  test('学生创建两个逾期分支样本并由辅导员审批通过', async ({ page }) => {
    overdueCloseLeaveId = await submitStudentLeave(page, {
      startDate: dates.overdueClose[0],
      endDate: dates.overdueClose[1],
      reason: `逾期三类处置点击验证 ${runId}`
    })
  })

  test('辅导员通过第一个逾期样本', async ({ page }) => {
    await approveOneDay(page, fixture, overdueCloseLeaveId)
  })

  test('学生创建第二个逾期补登记销假样本', async ({ page }) => {
    overdueProxyLeaveId = await submitStudentLeave(page, {
      startDate: dates.overdueProxy[0],
      endDate: dates.overdueProxy[1],
      reason: `逾期补登记销假点击验证 ${runId}`
    })
  })

  test('辅导员通过第二个逾期样本并把两个样本仅作时间前置', async ({ page }) => {
    await approveOneDay(page, fixture, overdueProxyLeaveId)
    backdateApprovedLeave(overdueCloseLeaveId, 4)
    backdateApprovedLeave(overdueProxyLeaveId, 2)
  })

  test('辅导员点击扫描逾期未销，两个 APPROVED 样本真实转为 OVERDUE', async ({ page }) => {
    const { affairs } = await loginMentor(page, fixture)
    await openFollowup(page, affairs, 'OVERDUE')
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/student-affairs/leave/scan-overdue'
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '扫描逾期未销' }).click()
    const body = await expectBusinessSuccess(await responsePromise, '扫描逾期未销')
    expect(Number(body?.data?.count || 0)).toBeGreaterThanOrEqual(2)

    await page.reload()
    await affairs.dismissGuideIfPresent()
    const first = await affairs.clickExactQueueLeave(overdueCloseLeaveId, '扫描后打开第一个 OVERDUE')
    expect(first.data.affairsStatus).toBe('OVERDUE')
    const second = await affairs.clickExactQueueLeave(overdueProxyLeaveId, '扫描后打开第二个 OVERDUE')
    expect(second.data.affairsStatus).toBe('OVERDUE')
  })

  test('逾期样本依次点击联系学生、转家校联系，状态均保持 OVERDUE', async ({ page }) => {
    await overdueHandle(page, fixture, overdueCloseLeaveId, 'CONTACT', 'OVERDUE', `已电话联系学生并完成留痕 ${runId}`)
  })

  test('同一逾期样本点击转家校联系继续留痕', async ({ page }) => {
    await overdueHandle(page, fixture, overdueCloseLeaveId, 'TO_HOME_SCHOOL', 'OVERDUE', `已转家校联系并记录处置过程 ${runId}`)
  })

  test('同一逾期样本点击处置完毕关闭后真实 CLOSED', async ({ page }) => {
    await overdueHandle(page, fixture, overdueCloseLeaveId, 'CLOSE', 'CLOSED', `已核实返校情况，逾期事项处置完毕 ${runId}`)
  })

  test('第二个逾期样本点击补登记销假进入 WAIT_CANCEL_LEAVE', async ({ page }) => {
    await proxyCancel(page, fixture, overdueProxyLeaveId, 'OVERDUE', '补登记销假', `逾期后已返校，补登记销假 ${runId}`)
  })

  test('辅导员确认逾期补登记销假样本最终 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, overdueProxyLeaveId)
  })

  test('学生提交 4 天请假，触发辅导员→学院二级审批', async ({ page }) => {
    mediumLeaveId = await submitStudentLeave(page, {
      startDate: dates.medium[0],
      endDate: dates.medium[1],
      reason: `四天二级审批真实点击验证 ${runId}`
    })
  })

  test('辅导员第一节点点击通过后必须进入 COLLEGE_REVIEW，而不是直接通过', async ({ page }) => {
    await approvalAction(page, fixture, {
      leaveId: mediumLeaveId,
      before: 'COUNSELOR_REVIEW',
      button: '通过',
      confirm: '通过',
      endpoint: 'approve',
      after: 'COLLEGE_REVIEW'
    })
  })

  test('校级管理员在真实 PC 审批页点击学院节点通过，二级请假最终 APPROVED', async ({ page }) => {
    await approvalAction(page, fixture, {
      leaveId: mediumLeaveId,
      account: 'admin',
      before: 'COLLEGE_REVIEW',
      button: '通过',
      confirm: '通过',
      endpoint: 'approve',
      after: 'APPROVED'
    })
  })

  test('学生销假关闭二级审批样本', async ({ page }) => {
    await studentSubmitCancel(page, mediumLeaveId, dates.medium[0], dates.medium[1])
  })

  test('辅导员确认二级审批样本销假为 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, mediumLeaveId)
  })

  test('学生提交 8 天请假，触发辅导员→学院→学工处三级审批', async ({ page }) => {
    majorLeaveId = await submitStudentLeave(page, {
      startDate: dates.major[0],
      endDate: dates.major[1],
      reason: `八天三级审批真实点击验证 ${runId}`
    })
  })

  test('三级请假第一节点由辅导员点击通过进入 COLLEGE_REVIEW', async ({ page }) => {
    await approvalAction(page, fixture, {
      leaveId: majorLeaveId,
      before: 'COUNSELOR_REVIEW',
      button: '通过',
      confirm: '通过',
      endpoint: 'approve',
      after: 'COLLEGE_REVIEW'
    })
  })

  test('三级请假第二节点点击通过进入 STUDENT_AFFAIRS_REVIEW', async ({ page }) => {
    await approvalAction(page, fixture, {
      leaveId: majorLeaveId,
      account: 'admin',
      before: 'COLLEGE_REVIEW',
      button: '通过',
      confirm: '通过',
      endpoint: 'approve',
      after: 'STUDENT_AFFAIRS_REVIEW'
    })
  })

  test('三级请假学工处节点再次真实点击通过后最终 APPROVED', async ({ page }) => {
    await approvalAction(page, fixture, {
      leaveId: majorLeaveId,
      account: 'admin',
      before: 'STUDENT_AFFAIRS_REVIEW',
      button: '通过',
      confirm: '通过',
      endpoint: 'approve',
      after: 'APPROVED'
    })
  })

  test('学生销假关闭三级审批样本', async ({ page }) => {
    await studentSubmitCancel(page, majorLeaveId, dates.major[0], dates.major[1])
  })

  test('辅导员确认三级审批样本销假为 CLOSED', async ({ page }) => {
    await counselorConfirmCancel(page, fixture, majorLeaveId)
  })

  test('学校管理员真实点击请假台账导出，必须创建真实导出结果/任务', async ({ page }) => {
    const { affairs } = await loginAdmin(page, fixture)
    await page.goto(`${config.staffBaseUrl.replace(/\/+$/, '')}/admin/student-affairs/leave/ledger`)
    await expect(page.getByText('请假台账').first()).toBeVisible()
    await affairs.dismissGuideIfPresent()

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/student-affairs/leave/export'
        && response.request().method() === 'POST'
    )
    const button = page.getByRole('button', { name: '导出 Excel 台账' })
    await expect(button).toBeEnabled()
    await button.click()
    const body = await expectBusinessSuccess(await responsePromise, '请假台账导出')
    const data = body?.data || {}
    expect(Boolean(data.jobId || data.filename || data.contentBase64), '导出必须返回 jobId 或真实 XLSX 结果').toBeTruthy()
    if (data.jobId) {
      await expect(page.getByText(new RegExp(`导出任务 #${data.jobId}`))).toBeVisible()
    }
  })
})
