import fs from 'node:fs'
import path from 'node:path'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const DESKTOP = { width: 1440, height: 1000 }
const STUDENT_NO = 'E2E20260002'
const EVIDENCE_DIR = path.resolve(process.cwd(), '../audit-evidence')

function marker() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const run = String(raw).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
  return `${run}-${process.pid}-${Date.now()}`
}

function writeClosure(code, evidence) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
  const payload = {
    code,
    productExactSha: process.env.PRODUCT_EXACT_SHA || '',
    browserFirst: true,
    status: 'REAL_PASS_CANDIDATE',
    evidence,
    writtenAt: new Date().toISOString()
  }
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, `v3-closure-${code.toLowerCase()}.json`),
    `${JSON.stringify(payload, null, 2)}\n`,
    'utf8'
  )
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function openStaffWorkspace(page, api, route) {
  await page.addInitScript((token) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, api.token)
  await page.goto(`${config.staffBaseUrl}${route}`)
  await dismissGuide(page)
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.innerWidth + 1)
}

async function findStudent(adminApi) {
  const rows = items(await adminApi.get('/students', {
    keyword: STUDENT_NO,
    page: 1,
    pageSize: 50
  }))
  const student = rows.find((row) => String(row.studentNo || row.loginName || '') === STUDENT_NO)
  if (!student?.id) throw new Error(`Student Affairs V3 student ${STUDENT_NO} not found`)
  return student
}

async function clickAndWaitForNext(row, page, action, nextAction) {
  await row.getByRole('button', { name: action, exact: true }).click()
  const confirm = page.getByRole('button', { name: action, exact: true }).last()
  if (await confirm.isVisible().catch(() => false)) await confirm.click()
  if (nextAction) await expect(row.getByRole('button', { name: nextAction, exact: true })).toBeVisible()
}

test.describe.serial('Student Affairs V3 domain hubs · Browser First closures', () => {
  let adminApi
  let student
  let dormBuildingId
  let dormBuildingName
  let dormBuildingCode
  let activityName
  let workStudyPostName
  let workStudyPostId
  let workStudyRecordId
  let loanBankName
  let loanId
  let feeReason
  let feeId
  let dormCheckTaskName
  let dormCheckTaskId
  let dormCheckDetail

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    student = await findStudent(adminApi)
    const id = marker()

    dormBuildingName = `SA-009 宿舍治理 ${id}`
    dormBuildingCode = `SA009-${id}`
    const building = await adminApi.post('/student-affairs/dorm/buildings', {
      buildingName: dormBuildingName,
      buildingCode: dormBuildingCode,
      genderLimit: 'MIXED',
      floors: 2,
      roomsPerFloor: 2,
      bedsPerRoom: 4
    })
    dormBuildingId = String(building?.buildingId || building?.id || '')
    expect(dormBuildingId).not.toBe('')

    const buildings = items(await adminApi.get('/student-affairs/dorm/buildings', { page: 1, pageSize: 200 }))
    const created = buildings.find((row) => String(row.buildingCode || '') === dormBuildingCode)
    expect(created, 'new SA-009 building must be listed').toBeTruthy()
    expect(Number(created.totalBeds)).toBe(16)
    expect(Number(created.vacantBeds)).toBe(16)

    activityName = `Playwright 第二课堂治理 ${id}`
    const activity = await adminApi.post('/student-affairs/activities', {
      activityName,
      activityType: 'ACTIVITY',
      location: 'Playwright 综合活动中心',
      quota: 30,
      creditType: 'SECOND_CLASS',
      creditValue: 2
    })
    expect(activity?.activityId).toBeTruthy()
    expect(String(activity?.status || '').toUpperCase()).toBe('DRAFT')

    workStudyPostName = `SA-006 图书馆助理 ${id}`
    const post = await adminApi.post('/student-affairs/work-study/posts', {
      deptName: 'E2E 学工处',
      postName: workStudyPostName,
      salary: '18.00',
      headcount: 2,
      requirement: 'SA-006 Browser First 正式岗位'
    })
    workStudyPostId = String(post?.postId || post?.id || '')
    expect(workStudyPostId).not.toBe('')
    await adminApi.post(`/student-affairs/work-study/posts/${workStudyPostId}/apply`, {
      studentId: Number(student.id)
    })
    const wsRows = items(await adminApi.get('/student-affairs/work-study/records', {
      postId: workStudyPostId,
      page: 1,
      pageSize: 50
    }))
    const ws = wsRows.find((row) => String(row.studentId) === String(student.id))
    workStudyRecordId = String(ws?.recordId || ws?.id || '')
    expect(workStudyRecordId).not.toBe('')
    expect(String(ws?.status || '').toUpperCase()).toBe('APPLIED')

    loanBankName = `SA007银行${id}`
    const loan = await adminApi.post('/student-affairs/loans', {
      studentId: Number(student.id),
      loanType: 'ORIGIN',
      bankName: loanBankName,
      bankLast4: '2607',
      yearCode: '2099-2100',
      amount: '8000.00'
    })
    loanId = String(loan?.loanId || loan?.id || '')
    expect(loanId).not.toBe('')
    expect(String(loan?.status || '').toUpperCase()).toBe('REGISTERED')

    feeReason = `SA-008 Browser First 临时困难补助 ${id}`
    const fee = await adminApi.post('/student-affairs/fee-reductions', {
      studentId: Number(student.id),
      itemType: 'TEMP_AID',
      amount: '600.00',
      reason: feeReason
    })
    feeId = String(fee?.feeId || fee?.id || '')
    expect(feeId).not.toBe('')
    expect(String(fee?.status || '').toUpperCase()).toBe('SUBMITTED')

    dormCheckTaskName = `SA-010 宿舍卫生检查 ${id}`
    dormCheckDetail = `SA-010 Browser First 异常整改 ${id}`
    const checkTask = await adminApi.post('/student-affairs/dorm/check-tasks', {
      taskName: dormCheckTaskName,
      checkType: 'HYGIENE',
      buildingId: Number(dormBuildingId)
    })
    dormCheckTaskId = String(checkTask?.taskId || checkTask?.id || '')
    expect(dormCheckTaskId).not.toBe('')
  })

  test('SA-006 Work-study applies, hires and onboards through real PC actions', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/funding/work-study')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/funding\/work-study/)
    await expect(page.getByRole('heading', { name: '勤工助学', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: workStudyPostName }).first()
    await expect(row).toBeVisible()
    await expect(row.getByRole('button', { name: '录用', exact: true })).toBeVisible()

    await row.getByRole('button', { name: '录用', exact: true }).click()
    await page.getByRole('button', { name: '确认录用', exact: true }).last().click()
    await expect(row.getByRole('button', { name: '确认上岗', exact: true })).toBeVisible()

    await row.getByRole('button', { name: '确认上岗', exact: true }).click()
    await page.getByRole('button', { name: '确认上岗', exact: true }).last().click()
    await expect(row.getByRole('button', { name: '月度考核', exact: true })).toBeVisible()

    await adminApi.post(`/student-affairs/work-study/records/${workStudyRecordId}/monthly`, {
      monthCode: '2099-08',
      workHours: '16.00',
      rating: 'GOOD',
      subsidyAmount: '288.00',
      remark: 'SA-006 Browser First 月度考核'
    })
    const current = items(await adminApi.get('/student-affairs/work-study/records', {
      postId: workStudyPostId,
      page: 1,
      pageSize: 50
    })).find((item) => String(item.recordId) === workStudyRecordId)
    expect(String(current?.status || '').toUpperCase()).toBe('ONBOARD')
    const monthly = items(await adminApi.get(`/student-affairs/work-study/records/${workStudyRecordId}/monthly`))
    expect(monthly.some((item) => String(item.monthCode) === '2099-08')).toBeTruthy()

    writeClosure('SA-006', {
      recordId: workStudyRecordId,
      finalStatus: 'ONBOARD',
      monthlyCode: '2099-08',
      browserActions: ['录用', '确认上岗']
    })
  })

  test('SA-007 Loan advances REGISTERED -> RECEIPT -> VERIFIED -> CONFIRMED in PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/funding/loans')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/funding\/loans/)
    await expect(page.getByRole('heading', { name: '助学贷款', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: loanBankName }).first()
    await expect(row).toBeVisible()
    await clickAndWaitForNext(row, page, '上传回执', '确认已核对')
    await clickAndWaitForNext(row, page, '确认已核对', '确认贷款')
    await clickAndWaitForNext(row, page, '确认贷款', null)
    await expect(row).toContainText('已确认')

    const current = items(await adminApi.get('/student-affairs/loans', { page: 1, pageSize: 50 }))
      .find((item) => String(item.loanId) === loanId)
    expect(String(current?.status || '').toUpperCase()).toBe('CONFIRMED')
    writeClosure('SA-007', {
      loanId,
      finalStatus: 'CONFIRMED',
      browserActions: ['上传回执', '确认已核对', '确认贷款']
    })
  })

  test('SA-008 Temporary aid is approved and issued through real PC actions', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/funding/fee-reductions')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/funding\/fee-reductions/)
    await expect(page.getByRole('heading', { name: '减免与临时补助', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: feeReason }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '批准', exact: true }).click()
    await expect(row.getByRole('button', { name: '发放', exact: true })).toBeVisible()
    await row.getByRole('button', { name: '发放', exact: true }).click()
    await expect(row).toContainText('已发放')

    const current = items(await adminApi.get('/student-affairs/fee-reductions', { page: 1, pageSize: 50 }))
      .find((item) => String(item.feeId) === feeId)
    expect(String(current?.status || '').toUpperCase()).toBe('ISSUED')
    writeClosure('SA-008', {
      feeId,
      finalStatus: 'ISSUED',
      browserActions: ['批准', '发放']
    })
  })

  test('SA-009 Dormitory management shows the uniquely created building', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dormitory')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/dormitory/)
    await expect(page.getByRole('heading', { name: '宿舍管理', exact: true })).toBeVisible()
    await expect(page.getByText(dormBuildingName, { exact: true })).toHaveCount(1)
    await expect(page.getByText(dormBuildingName, { exact: true })).toBeVisible()
    await expect(page.getByText('总床位', { exact: true })).toBeVisible()
    await expect(page.getByText('房间管理', { exact: true })).toBeVisible()
    await expect(page.getByText('床位管理 / 入住退宿', { exact: true })).toBeVisible()

    const archive = page.locator('.app-desc-list').last()
    const assignItem = archive.locator('.app-desc-list__item').first()
    const assignValue = assignItem.locator('.app-desc-list__value')
    await expect(assignValue).toContainText('COUNSELOR_ASSIGN')
    await expectNoHorizontalOverflow(page)
  })

  test('SA-009 Dormitory archive remains readable at 1024px', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 900 })
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dormitory')

    const archive = page.locator('.app-desc-list').last()
    await expect(archive).toBeVisible()
    const columns = await archive.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length)
    expect(columns).toBe(1)
    await expect(archive.locator('.app-desc-list__value').first()).toContainText('COUNSELOR_ASSIGN')
    await expectNoHorizontalOverflow(page)
  })

  test('SA-010 Dorm inspection records a real abnormal result in PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dorm/check')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/dorm\/check/)
    await expect(page.getByRole('heading', { name: '宿舍检查', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: dormCheckTaskName }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '录结果', exact: true }).click()
    const detail = page.getByPlaceholder('写清问题、处理动作与整改要求')
    await expect(detail).toBeVisible()
    await detail.fill(dormCheckDetail)
    await page.getByRole('button', { name: '提交', exact: true }).last().click()

    const records = items(await adminApi.get(`/student-affairs/dorm/check-tasks/${dormCheckTaskId}/records`, {
      page: 1,
      pageSize: 100
    }))
    const record = records.find((item) => String(item.detail || '') === dormCheckDetail)
    expect(record, 'SA-010 abnormal inspection record must persist').toBeTruthy()
    expect(String(record.result || '').toUpperCase()).toBe('ABNORMAL')

    await row.getByRole('button', { name: '记录', exact: true }).click()
    await expect(page.getByText(dormCheckDetail, { exact: true })).toBeVisible()
    writeClosure('SA-010', {
      taskId: dormCheckTaskId,
      recordId: String(record.recordId || record.id || ''),
      result: 'ABNORMAL',
      browserActions: ['录结果', '记录']
    })
  })

  test('SA-015 Student activity real draft state', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity/)
    await expect(page.getByRole('heading', { name: '学生活动管理', exact: true })).toBeVisible()
    const row = page.locator('tbody tr').filter({ hasText: activityName }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('草稿')
    await expect(row).toContainText('2')
  })

  test('SA-014 Mental attention privacy-governed workspace', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/mental')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/mental/)
    await expect(page.getByRole('heading', { name: '心理关注名单', exact: true })).toBeVisible()
    await expect(page.locator('.mental-privacy-summary')).toBeVisible()
    await expect(page.locator('.sa-workflow-strip')).toBeVisible()
    await expect(page.getByText('关注名单（明细默认遮蔽）', { exact: true })).toBeVisible()
    await expect(page.getByText(/逐生授权|明细默认脱敏/).first()).toBeVisible()
  })
})
