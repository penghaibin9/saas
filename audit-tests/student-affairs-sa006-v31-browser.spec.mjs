import fs from 'node:fs'
import path from 'node:path'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const STUDENT_NO = 'E2E20260002'
const EVIDENCE_DIR = path.resolve(process.cwd(), '../audit-evidence')
const COUNSELOR_B = {
  tenant: 'sandbox-school',
  username: 'e2e_counselor_b',
  password: 'E2eTest@2026'
}

function marker() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const run = String(raw).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
  return `${run}-${process.pid}-${Date.now()}`
}

function writeClosure(evidence) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, 'v3-closure-sa-006.json'),
    `${JSON.stringify({
      code: 'SA-006',
      productExactSha: process.env.PRODUCT_EXACT_SHA || '',
      browserFirst: true,
      status: 'REAL_PASS_CANDIDATE',
      evidence,
      writtenAt: new Date().toISOString()
    }, null, 2)}\n`,
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

async function openStaffWorkspace(page, api) {
  await page.addInitScript((token) => window.sessionStorage.setItem('gx_pc_token_v1', token), api.token)
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding/work-study`)
  await dismissGuide(page)
}

async function findStudent(adminApi) {
  const rows = items(await adminApi.get('/students', { keyword: STUDENT_NO, page: 1, pageSize: 50 }))
  const row = rows.find((item) => String(item.studentNo || item.loginName || '') === STUDENT_NO)
  if (!row?.id) throw new Error(`SA-006 student ${STUDENT_NO} not found`)
  return row
}

test.describe.serial('SA-006 勤工助学 · exact-head Browser First', () => {
  let adminApi
  let demoAdminApi
  let counselorBApi
  let student
  let postId
  let postName
  let recordId

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    demoAdminApi = await loginApi(config.demoAdmin)
    counselorBApi = await loginApi(COUNSELOR_B)
    student = await findStudent(adminApi)
    const id = marker()
    postName = `SA-006 图书馆助理 ${id}`

    const post = await adminApi.post('/student-affairs/work-study/posts', {
      deptName: 'E2E 学工处',
      postName,
      salary: '18.00',
      headcount: 2,
      requirement: 'SA-006 V3.1 Browser First 正式岗位'
    })
    postId = String(post?.postId || post?.id || '')
    expect(postId).not.toBe('')

    await adminApi.post(`/student-affairs/work-study/posts/${postId}/apply`, {
      studentId: Number(student.id)
    })
    const rows = items(await adminApi.get('/student-affairs/work-study/records', {
      postId,
      page: 1,
      pageSize: 50
    }))
    const current = rows.find((item) => String(item.studentId) === String(student.id))
    recordId = String(current?.recordId || current?.id || '')
    expect(recordId).not.toBe('')
    expect(String(current?.status || '').toUpperCase()).toBe('APPLIED')
  })

  test('Browser: 录用 → 上岗 → 月度考核全部由真实 Staff PC 完成', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await openStaffWorkspace(page, adminApi)
    await expect(page).toHaveURL(/\/admin\/student-affairs\/funding\/work-study/)
    await expect(page.getByRole('heading', { name: '勤工助学', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: postName }).first()
    await expect(row).toBeVisible()

    await row.getByRole('button', { name: '录用', exact: true }).click()
    await page.getByRole('button', { name: '确认录用', exact: true }).last().click()
    await expect(row.getByRole('button', { name: '确认上岗', exact: true })).toBeVisible()

    await row.getByRole('button', { name: '确认上岗', exact: true }).click()
    await page.getByRole('button', { name: '确认上岗', exact: true }).last().click()
    await expect(row.getByRole('button', { name: '月度考核', exact: true })).toBeVisible()

    await row.getByRole('button', { name: '月度考核', exact: true }).click()
    await page.getByPlaceholder('YYYY-MM').fill('2099-08')
    const visibleNumbers = page.locator('input[type="number"]:visible')
    await expect(visibleNumbers).toHaveCount(2)
    await visibleNumbers.nth(0).fill('16')
    await page.locator('select:visible').last().selectOption('GOOD')
    await visibleNumbers.nth(1).fill('288')
    await page.getByRole('button', { name: '保存考核', exact: true }).last().click()

    await expect(row).toContainText('288')
    const records = items(await adminApi.get('/student-affairs/work-study/records', { postId, page: 1, pageSize: 50 }))
    const current = records.find((item) => String(item.recordId || item.id) === recordId)
    expect(String(current?.status || '').toUpperCase()).toBe('ONBOARD')
    expect(Number(current?.subsidyTotal || current?.subsidy_total || 0)).toBe(288)

    const monthly = items(await adminApi.get(`/student-affairs/work-study/records/${recordId}/monthly`))
    const month = monthly.find((item) => String(item.monthCode || item.month_code) === '2099-08')
    expect(month).toBeTruthy()
    expect(String(month?.rating || '').toUpperCase()).toBe('GOOD')
    expect(Number(month?.subsidyAmount || month?.subsidy_amount || 0)).toBe(288)
  })

  test('Data-scope negative: 2402辅导员看不到2401学生的勤工记录', async () => {
    const records = items(await counselorBApi.get('/student-affairs/work-study/records', { page: 1, pageSize: 200 }))
    expect(records.some((item) => String(item.recordId || item.id) === recordId)).toBeFalsy()
    expect(records.some((item) => String(item.studentNo || '') === STUDENT_NO)).toBeFalsy()
  })

  test('Tenant negative: 另一租户管理员看不到本租户岗位与记录', async () => {
    const posts = items(await demoAdminApi.get('/student-affairs/work-study/posts', { page: 1, pageSize: 200 }))
    expect(posts.some((item) => String(item.postName || '') === postName)).toBeFalsy()
    const records = items(await demoAdminApi.get('/student-affairs/work-study/records', { page: 1, pageSize: 200 }))
    expect(records.some((item) => String(item.recordId || item.id) === recordId)).toBeFalsy()
  })

  test('API truth marker: 当前租户只读回读仍保持正式终态', async () => {
    const records = items(await adminApi.get('/student-affairs/work-study/records', { postId, page: 1, pageSize: 50 }))
    const current = records.find((item) => String(item.recordId || item.id) === recordId)
    expect(String(current?.status || '').toUpperCase()).toBe('ONBOARD')
    const monthly = items(await adminApi.get(`/student-affairs/work-study/records/${recordId}/monthly`))
    expect(monthly.some((item) => String(item.monthCode || item.month_code) === '2099-08')).toBeTruthy()

    writeClosure({
      tenant: config.sandboxAdmin.tenant,
      studentNo: STUDENT_NO,
      postId,
      postName,
      recordId,
      finalStatus: 'ONBOARD',
      monthlyCode: '2099-08',
      monthlyRating: 'GOOD',
      subsidyAmount: 288,
      browserActions: ['录用', '确认上岗', '月度考核', '保存考核'],
      dataScopeNegative: true,
      tenantNegative: true
    })
  })
})
