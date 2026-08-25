import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const accounts = {
  saAdmin: { tenant: 'sandbox-school', username: 'e2e_sa_admin', password: 'E2eTest@2026' },
  counselor: { tenant: 'sandbox-school', username: 'e2e_sa009_counselor', password: 'E2eTest@2026' },
  dormManager: { tenant: 'sandbox-school', username: 'e2e_sa009_dorm', password: 'E2eTest@2026' }
}
const studentNo = 'E2E20260911'
const studentName = 'SA009宿舍学生'

function field(dialog, label) {
  return dialog.locator('.app-form-item').filter({ hasText: label }).first()
}

async function jsonBody(response) {
  try { return await response.json() } catch { return {} }
}

async function selectRemote(root, { searchPlaceholder, keyword, optionText }) {
  await root.getByRole('combobox').click()
  const search = root.getByPlaceholder(searchPlaceholder)
  if (keyword) await search.fill(keyword)
  const option = root.getByRole('option').filter({ hasText: optionText }).first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
}

async function selectOpenPicker(page, index, optionText) {
  const combo = page.getByRole('combobox').nth(index)
  await combo.click()
  const option = page.getByRole('option').filter({ hasText: optionText }).first()
  await expect(option).toBeVisible({ timeout: 20_000 })
  await option.click()
}

async function loginAs(page, account) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(account)
  return login
}

test.describe.serial('Student Affairs V3 Browser First · SA-009 dorm lifecycle', () => {
  test.describe.configure({ retries: 0 })

  test('real Staff PC creates managed dorm, checks in, transfers through real assignees, then checks out', async ({ page }) => {
    test.setTimeout(300_000)
    const prefix = `E2E-SA009-${Date.now()}-${process.pid}`
    const buildingName = `${prefix}-宿舍楼`
    const api500 = []
    const consoleErrors = []

    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      }
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push(text)
    })

    await loginAs(page, accounts.saAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dorm/resource`)
    await expect(page.getByRole('heading', { name: '房源管理', exact: true })).toBeVisible()

    let buildingId = ''
    await test.step('Staff PC creates building and assigns real DORM_MANAGER through role-filtered picker', async () => {
      await page.getByRole('button', { name: '新建楼栋', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '新增楼栋' })
      await expect(dialog).toBeVisible()
      await field(dialog, '楼栋名称').locator('input').fill(buildingName)
      await field(dialog, '性别限制').locator('select').selectOption('MALE')
      await selectRemote(field(dialog, '负责宿管'), {
        searchPlaceholder: '按工号 / 姓名搜索',
        keyword: 'e2e_sa009_dorm',
        optionText: 'e2e_sa009_dorm'
      })

      const responsePromise = page.waitForResponse((response) => {
        try {
          const url = new URL(response.url())
          return url.pathname.endsWith('/api/v1/student-affairs/dorm/buildings')
            && response.request().method() === 'POST'
        } catch { return false }
      })
      await dialog.getByRole('button', { name: '新增', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `building create HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      buildingId = String(env.data?.buildingId || '')
      expect(buildingId).toBeTruthy()
      await expect(dialog).toBeHidden()
      await expect(page.getByText(buildingName, { exact: true })).toBeVisible({ timeout: 20_000 })
    })

    await test.step('Staff PC uses real layout button to create one room with two beds', async () => {
      const row = page.locator('tbody tr').filter({ hasText: buildingName }).first()
      await expect(row).toBeVisible()
      await row.getByRole('button', { name: '铺床', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: /一键铺满/ })
      await expect(dialog).toBeVisible()
      await field(dialog, '层数').locator('input').fill('1')
      await field(dialog, '每层房数').locator('input').fill('1')
      await field(dialog, '每间床位').locator('input').fill('2')
      const responsePromise = page.waitForResponse((response) =>
        response.url().includes(`/api/v1/student-affairs/dorm/buildings/${buildingId}/generate`)
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '铺满', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `layout generate HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      expect(Number(env.data?.bedsCreated)).toBe(2)
      await expect(dialog).toBeHidden()
    })

    let oldBedId = ''
    await test.step('Staff PC checks the student into the first real vacant bed', async () => {
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dorm/checkin`)
      await expect(page.getByRole('heading', { name: '入住管理', exact: true })).toBeVisible()
      await selectOpenPicker(page, 0, buildingName)
      await page.waitForTimeout(300)
      const roomCombo = page.getByRole('combobox').nth(1)
      await roomCombo.click()
      const roomOption = page.getByRole('option').first()
      await expect(roomOption).toBeVisible({ timeout: 20_000 })
      await roomOption.click()
      const checkin = page.getByRole('button', { name: '入住', exact: true }).first()
      await expect(checkin).toBeVisible({ timeout: 20_000 })
      await checkin.click()
      const dialog = page.getByRole('dialog', { name: /办理入住/ })
      await selectRemote(field(dialog, '入住学生'), {
        searchPlaceholder: '按学号 / 姓名搜索', keyword: studentNo, optionText: studentNo
      })
      const responsePromise = page.waitForResponse((response) =>
        /\/api\/v1\/student-affairs\/dorm\/beds\/\d+\/checkin$/.test(new URL(response.url()).pathname)
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '确认入住', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `checkin HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      oldBedId = String(env.data?.bedId || '')
      expect(oldBedId).toBeTruthy()
      await expect(page.getByText(studentName, { exact: true })).toBeVisible({ timeout: 20_000 })
    })

    let transferId = ''
    let fromBedId = ''
    let toBedId = ''
    await test.step('Staff PC submits real transfer to the remaining vacant bed', async () => {
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dorm/transfer`)
      await expect(page.getByRole('heading', { name: '调宿与退宿', exact: true })).toBeVisible()
      await page.getByRole('button', { name: '发起调宿', exact: true }).first().click()
      const dialog = page.getByRole('dialog', { name: '发起调宿' })
      await selectRemote(field(dialog, '调宿学生'), {
        searchPlaceholder: '按学号 / 姓名搜索', keyword: studentNo, optionText: studentNo
      })
      await selectRemote(field(dialog, '目标楼栋'), {
        searchPlaceholder: '按名称搜索', keyword: buildingName, optionText: buildingName
      })
      await selectRemote(field(dialog, '目标房间'), {
        searchPlaceholder: '按名称搜索', keyword: '', optionText: '101'
      })
      const bedField = field(dialog, '目标床位')
      await bedField.getByRole('combobox').click()
      const targetOption = bedField.getByRole('option').first()
      await expect(targetOption).toBeVisible({ timeout: 20_000 })
      await targetOption.click()
      await field(dialog, '调宿事由').locator('textarea').fill('SA-009真实浏览器调宿验收：验证辅导员与宿管两级审批及床位切换')

      const responsePromise = page.waitForResponse((response) =>
        response.url().endsWith('/api/v1/student-affairs/dorm/transfers')
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '核对并提交', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `transfer submit HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      transferId = String(env.data?.transferId || '')
      fromBedId = String(env.data?.fromBedId || '')
      toBedId = String(env.data?.toBedId || '')
      expect(transferId).toBeTruthy()
      expect(fromBedId).toBe(oldBedId)
      expect(toBedId).toBeTruthy()
      expect(toBedId).not.toBe(fromBedId)
      expect(env.data?.status).toBe('COUNSELOR_REVIEW')
    })

    await test.step('assigned counselor logs in and approves only the counselor node', async () => {
      await loginAs(page, accounts.counselor)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dorm/transfer`)
      await expect(page.getByRole('heading', { name: '调宿与退宿', exact: true })).toBeVisible()
      const row = page.locator('tbody tr').filter({ hasText: studentNo }).first()
      await expect(row).toBeVisible({ timeout: 20_000 })
      await row.getByRole('button', { name: '核对后通过', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '确认通过调宿申请' })
      const responsePromise = page.waitForResponse((response) =>
        response.url().includes(`/api/v1/student-affairs/dorm/transfers/${transferId}/review`)
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '确认通过', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `counselor review HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      expect(env.data?.status).toBe('DORM_MANAGER_REVIEW')
    })

    await test.step('real assigned dorm manager logs in, sees scoped todo and executes transfer', async () => {
      await loginAs(page, accounts.dormManager)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dorm/transfer`)
      await expect(page.getByRole('heading', { name: '调宿与退宿', exact: true })).toBeVisible()
      const row = page.locator('tbody tr').filter({ hasText: studentNo }).first()
      await expect(row).toBeVisible({ timeout: 20_000 })
      await row.getByRole('button', { name: '核对后通过', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '确认通过调宿申请' })
      const responsePromise = page.waitForResponse((response) =>
        response.url().includes(`/api/v1/student-affairs/dorm/transfers/${transferId}/review`)
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '确认通过', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `dorm-manager review HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      expect(env.data?.status).toBe('EXECUTED')
    })

    await test.step('dorm manager verifies moved occupant in UI and performs real checkout', async () => {
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dorm/checkin`)
      await expect(page.getByRole('heading', { name: '入住管理', exact: true })).toBeVisible()
      await selectOpenPicker(page, 0, buildingName)
      const roomCombo = page.getByRole('combobox').nth(1)
      await roomCombo.click()
      const roomOption = page.getByRole('option').first()
      await expect(roomOption).toBeVisible({ timeout: 20_000 })
      await roomOption.click()
      await expect(page.getByText(studentName, { exact: true })).toBeVisible({ timeout: 20_000 })
      const checkout = page.getByRole('button', { name: '退宿', exact: true }).first()
      await expect(checkout).toBeVisible()
      await checkout.click()
      const dialog = page.getByRole('dialog', { name: '办理退宿' })
      const responsePromise = page.waitForResponse((response) =>
        response.url().includes(`/api/v1/student-affairs/dorm/beds/${toBedId}/checkout`)
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '确认退宿', exact: true }).click()
      const response = await responsePromise
      expect(response.ok(), `checkout HTTP ${response.status()}`).toBeTruthy()
      const env = await jsonBody(response)
      expect(env.code).toBe(0)
      expect(env.data?.status).toBe('VACANT')
      await expect(page.getByText(studentName, { exact: true })).toHaveCount(0, { timeout: 20_000 })
    })

    expect(api500, 'no API 5xx during SA-009 browser lifecycle').toEqual([])
    expect(consoleErrors, 'no unexpected browser console errors during SA-009 browser lifecycle').toEqual([])

    await fs.writeFile(
      path.resolve('student-affairs-sa009-browser-v3-evidence.json'),
      JSON.stringify({
        exactHead: process.env.E2E_TARGET_SHA || '',
        buildingName,
        buildingId,
        studentNo,
        transferId,
        oldBedId: fromBedId,
        newBedId: toBedId,
        counselorLogin: accounts.counselor.username,
        dormManagerLogin: accounts.dormManager.username,
        managerBindingSurface: 'STAFF_PC_REAL_PICKER',
        lifecycle: ['BUILDING_CREATE', 'LAYOUT_GENERATE', 'CHECKIN', 'TRANSFER_SUBMIT', 'COUNSELOR_APPROVE', 'DORM_MANAGER_APPROVE', 'CHECKOUT'],
        result: 'REAL_PASS'
      }, null, 2),
      'utf8'
    )
  })
})
