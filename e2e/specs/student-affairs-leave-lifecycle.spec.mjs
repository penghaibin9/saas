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
  expect(response.ok(), `${action} returned HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  if (body && Object.prototype.hasOwnProperty.call(body, 'code')) {
    expect(body.code, `${action} returned business error: ${text.slice(0, 800)}`).toBe(0)
  }
  return body
}

function isLeaveDetailResponse(response) {
  return /^\/api\/v1\/student-affairs\/leave\/[^/]+$/.test(apiPath(response))
    && response.request().method() === 'GET'
}

test.describe('学工请假生产交互闭环', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let leaveId = ''
  let outsideLeaveId = ''
  let returnedLeaveId = ''
  let reason = ''
  let outsideReason = ''
  let returnedReason = ''
  let revisedReason = ''
  let extensionReason = ''
  let startDate = ''
  let endDate = ''
  let returnedStartDate = ''
  let returnedEndDate = ''
  let extendedEndDate = ''

  test.beforeAll(async () => {
    fixture = await loadStudentAffairsFixture()
    const runId = String(process.env.GITHUB_RUN_ID || Date.now()).replace(/\D/g, '').slice(-12)
    reason = `Playwright 学工请假交互验证 ${runId}`
    outsideReason = `Playwright 跨班级不可见验证 ${runId}`
    returnedReason = `请补充离校安排后重新提交 ${runId}`
    revisedReason = `已补充具体离校安排并重新提交 ${runId}`
    extensionReason = `返程计划调整申请续假一天 ${runId}`
    startDate = localDate(1)
    endDate = localDate(1)
    returnedStartDate = localDate(3)
    returnedEndDate = localDate(3)
    extendedEndDate = localDate(4)
  })

  test('学生 PC 请假表单先做交互校验且不产生业务写入', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.assertLeaveFormValidation({ startDate, endDate })
  })

  test('其他行政班学生 PC 真实提交请假作为越权负向样本', async ({ page }) => {
    expect(String(fixture.outsideClassId)).not.toBe(String(fixture.classId))
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.outsideStudent)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    outsideLeaveId = await affairs.submitLeave({
      startDate,
      endDate,
      reason: outsideReason
    })
    expect(outsideLeaveId).not.toBe('')
  })

  test('辅导员 PC 待审队列看不到其他行政班学生请假', async ({ page }) => {
    expect(outsideLeaveId, '前序跨班级学生提交步骤必须返回 leave id').not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.assertOutsideLeaveNotVisible(outsideLeaveId)
  })

  test('学生 PC 真实提交本人行政班普通请假', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    leaveId = await affairs.submitLeave({
      startDate,
      endDate,
      reason
    })
    expect(leaveId).not.toBe('')
  })

  test('辅导员 PC 审批本人负责班级的精确请假单', async ({ page }) => {
    expect(leaveId, '前序学生提交步骤必须返回 leave id').not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.approve(leaveId)
  })

  test('学生 PC 取消销假确认时保持已通过且不产生写入', async ({ page }) => {
    expect(leaveId, '前序学生提交步骤必须返回 leave id').not.toBe('')
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.dismissCancelAndStay({ leaveId })
  })

  test('学生 PC 对已通过请假真实申请销假', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.submitCancel({ leaveId })
  })

  test('辅导员 PC 真实确认销假并关闭请假', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.confirmCancel(leaveId)
  })

  test('学生 PC 同步看到已销假终态且非法操作入口消失', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.verifyClosedAsStudent({ startDate })
  })

  test('学校管理员 PC 核验 CLOSED 终态与四段审批留痕', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.sandboxAdmin)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.verifyFinalAsAdmin(leaveId)
  })

  test('学生 PC 再真实提交一张请假用于退回重提链路', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    returnedLeaveId = await affairs.submitLeave({
      startDate: returnedStartDate,
      endDate: returnedEndDate,
      reason: `待老师退回修改的请假 ${Date.now()}`
    })
    expect(returnedLeaveId).not.toBe('')
    expect(returnedLeaveId).not.toBe(leaveId)
  })

  test('辅导员 PC 真实退回请假并填写可见退回意见', async ({ page }) => {
    expect(returnedLeaveId, '前序第二张请假必须返回 leave id').not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.openApproval()
    const { data } = await affairs.clickExactQueueLeave(returnedLeaveId, '辅导员打开待退回请假详情')
    expect(data.affairsStatus).toBe('COUNSELOR_REVIEW')

    const action = page.locator('.lv-foot').getByRole('button', { name: '退回重提' })
    await expect(action).toBeEnabled()
    await action.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('退回重提')
    await dialog.locator('textarea').fill(returnedReason)

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/student-affairs/leave/${returnedLeaveId}/return`
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '退回' }).click()
    const body = await expectBusinessSuccess(await responsePromise, '辅导员退回请假重提')
    expect(body?.data?.affairsStatus).toBe('RETURNED')
    expect(body?.data?.returnReason).toBe(returnedReason)
  })

  test('学生 PC 看到退回意见并真实修改后重新提交', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.openLeave()

    const editButton = page.getByRole('button', { name: '修改后重提' })
    await expect(editButton).toHaveCount(1)
    const record = editButton.locator('xpath=ancestor::article[contains(@class,"record")]')
    await expect(record).toContainText(returnedReason)
    await expect(record).toContainText(/已退回|RETURNED/)

    const editablePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/mobile/affairs/leave/${returnedLeaveId}/editable`
      && response.request().method() === 'GET'
    )
    await editButton.click()
    const editable = await expectBusinessSuccess(await editablePromise, '学生读取退回请假可编辑内容')
    expect(String(editable?.data?.id || '')).toBe(String(returnedLeaveId))
    expect(editable?.data?.affairsStatus).toBe('RETURNED')

    const modal = page.locator('.mask .modal')
    await expect(modal).toBeVisible()
    await expect(modal).toContainText('修改退回请假')
    await expect(modal).toContainText(returnedReason)
    await modal.locator('textarea').fill(revisedReason)

    const updatePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/mobile/affairs/leave/${returnedLeaveId}/returned`
      && response.request().method() === 'PUT'
    )
    const resubmitPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/portal/affairs/leave/${returnedLeaveId}/resubmit`
      && response.request().method() === 'POST'
    )
    await modal.getByRole('button', { name: '保存并提交' }).click()
    const updated = await expectBusinessSuccess(await updatePromise, '学生保存退回请假修改')
    expect(updated?.data?.affairsStatus).toBe('RETURNED')
    expect(updated?.data?.reason).toBe(revisedReason)
    const resubmitted = await expectBusinessSuccess(await resubmitPromise, '学生重新提交退回请假')
    expect(resubmitted?.data?.affairsStatus).toBe('COUNSELOR_REVIEW')
    expect(resubmitted?.data?.returnReason || '').toBe('')
    expect(resubmitted?.data?.reason).toBe(revisedReason)
    await expect(modal).toBeHidden()
    await expect(page.getByRole('button', { name: '修改后重提' })).toHaveCount(0)
  })

  test('辅导员 PC 对重新提交的同一请假再次审批通过', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)
    await affairs.approve(returnedLeaveId)
  })

  test('学生 PC 对再次通过的请假真实申请续假', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.openLeave()

    const buttons = page.getByRole('button', { name: '申请续假' })
    await expect(buttons).toHaveCount(1)
    const button = buttons.first()
    const record = button.locator('xpath=ancestor::article[contains(@class,"record")]')
    await expect(record).toContainText(returnedEndDate)
    await expect(record).toContainText(/已通过|APPROVED/)
    await button.click()

    const inline = record.locator('.inline-form')
    await expect(inline).toBeVisible()
    await expect(inline).toContainText('原结束日期')
    await expect(inline).toContainText(returnedEndDate)
    await inline.locator('input[type="date"]').fill(extendedEndDate)
    await inline.locator('textarea').fill(extensionReason)
    const submit = inline.getByRole('button', { name: '提交续假' })
    await expect(submit).toBeEnabled()

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/portal/affairs/leave/${returnedLeaveId}/extension`
      && response.request().method() === 'POST'
    )
    await submit.click()
    const body = await expectBusinessSuccess(await responsePromise, '学生提交续假申请')
    expect(body?.data?.affairsStatus).toBe('EXTENSION_REVIEW')
    expect(String(body?.data?.endTime || '')).toContain(returnedEndDate)
    await expect(page.getByRole('button', { name: '申请续假' })).toHaveCount(0)
  })

  test('辅导员 PC 真实审批续假并把新结束时间写回主请假', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/辅导员|COUNSELOR/)
    const affairs = new StaffStudentAffairsLeavePage(page, config.staffBaseUrl, fixture)

    await page.goto(`${config.staffBaseUrl.replace(/\/+$/, '')}/admin/student-affairs/leave/followup?status=EXTENSION_REVIEW`)
    await expect(page.getByText('延期销假').first()).toBeVisible()
    await affairs.dismissGuideIfPresent()
    const { data } = await affairs.clickExactQueueLeave(returnedLeaveId, '辅导员打开待续假详情')
    expect(data.affairsStatus).toBe('EXTENSION_REVIEW')
    const extension = (data.extensions || []).find((item) => item.status === 'SUBMITTED')
    expect(extension, '续假详情必须包含 SUBMITTED 续假记录').toBeTruthy()
    expect(String(extension.oldEndTime || '')).toContain(returnedEndDate)
    expect(String(extension.newEndTime || '')).toContain(extendedEndDate)
    expect(extension.reason).toBe(extensionReason)

    const action = page.locator('.lv-foot').getByRole('button', { name: '续假通过' })
    await expect(action).toBeEnabled()
    await action.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('续假通过')

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/student-affairs/leave/${returnedLeaveId}/extension-approve`
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '通过续假' }).click()
    const body = await expectBusinessSuccess(await responsePromise, '辅导员审批续假')
    expect(body?.data?.affairsStatus).toBe('APPROVED')
    expect(String(body?.data?.endTime || '')).toContain(extendedEndDate)
    expect(String(body?.data?.expectedReturnAt || '')).toContain(extendedEndDate)
  })

  test('学生 PC 最终看到续假后的新结束日期且仍处于已通过', async ({ page }) => {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    const affairs = new StudentAffairsPortalPage(page, config.studentBaseUrl, fixture)
    await affairs.openLeave()

    const button = page.getByRole('button', { name: '申请续假' })
    await expect(button).toHaveCount(1)
    const record = button.locator('xpath=ancestor::article[contains(@class,"record")]')
    await expect(record).toContainText(returnedStartDate)
    await expect(record).toContainText(extendedEndDate)
    await expect(record).toContainText(/已通过|APPROVED/)
    await expect(record.getByRole('button', { name: '修改后重提' })).toHaveCount(0)
  })

  test('学校管理员 PC 核验退回重提与续假的完整事实和审计链', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.sandboxAdmin)
    const query = new URLSearchParams({ studentId: fixture.studentId, status: 'APPROVED' })
    await page.goto(`${config.staffBaseUrl.replace(/\/+$/, '')}/admin/student-affairs/leave/ledger?${query}`)
    await expect(page.getByText('请假台账').first()).toBeVisible()

    const buttons = page.getByRole('button', { name: '查看' })
    await expect(buttons.first()).toBeVisible()
    const count = await buttons.count()
    let data = null
    for (let index = 0; index < count; index += 1) {
      const detailResponse = page.waitForResponse(isLeaveDetailResponse)
      await buttons.nth(index).click()
      const body = await expectBusinessSuccess(await detailResponse, '管理员打开退回重提与续假台账详情')
      if (String(body?.data?.id || '') === String(returnedLeaveId)) {
        data = body.data
        break
      }
      await page.keyboard.press('Escape')
    }

    expect(data, `请假台账未找到退回重提目标记录 ${returnedLeaveId}`).toBeTruthy()
    expect(data.affairsStatus).toBe('APPROVED')
    expect(data.reason).toBe(revisedReason)
    expect(data.returnReason || '').toBe('')
    expect(String(data.endTime || '')).toContain(extendedEndDate)
    expect(String(data.expectedReturnAt || '')).toContain(extendedEndDate)

    const extensions = data.extensions || []
    expect(extensions).toHaveLength(1)
    expect(extensions[0].status).toBe('APPROVED')
    expect(String(extensions[0].oldEndTime || '')).toContain(returnedEndDate)
    expect(String(extensions[0].newEndTime || '')).toContain(extendedEndDate)
    expect(extensions[0].reason).toBe(extensionReason)

    const actions = (data.auditTrail || []).map((item) => item.action)
    for (const action of [
      'APPLY', 'RETURNED', 'STUDENT_EDIT_RETURNED', 'RESUBMIT',
      'APPROVED', 'EXTENSION_SUBMIT', 'EXTENSION_APPROVED'
    ]) {
      expect(actions, `管理员审计链缺少 ${action}`).toContain(action)
    }
  })
})
