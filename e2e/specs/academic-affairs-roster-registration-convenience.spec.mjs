import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../..')
const statePath = path.join(repoRoot, 'backend/tmp/e2e_academic_aa002_state.local.json')
const outcomePath = path.resolve(here, '../academic-aa002-browser-outcome.json')

function fixture() { return JSON.parse(fs.readFileSync(statePath, 'utf8')) }

async function dismissPageGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: '跳过引导' }).click()
    await expect(mask).toBeHidden()
  }
}

async function browserApi(page, token, method, requestPath, body) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, pathValue, requestBody }) => {
    const response = await fetch(`${apiBaseUrl}${pathValue}`, {
      method: requestMethod,
      headers: { Accept: 'application/json', Authorization: `Bearer ${tokenValue}`,
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody)
    })
    const text = await response.text()
    let json = null
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 500) } }
    return { status: response.status, json }
  }, { apiBaseUrl: config.apiBaseUrl, tokenValue: token, requestMethod: method, pathValue: requestPath, requestBody: body })
}

async function browserUploadXlsx(page, token, requestPath, xlsxFile) {
  const base64 = fs.readFileSync(xlsxFile).toString('base64')
  return page.evaluate(async ({ apiBaseUrl, tokenValue, pathValue, fileBase64 }) => {
    const raw = atob(fileBase64)
    const bytes = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
    const form = new FormData()
    form.append('file', new File([bytes], 'aa002-roster-import.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }))
    const response = await fetch(`${apiBaseUrl}${pathValue}`, {
      method: 'POST', headers: { Accept: 'application/json', Authorization: `Bearer ${tokenValue}` }, body: form
    })
    const text = await response.text()
    let json = null
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 500) } }
    return { status: response.status, json }
  }, { apiBaseUrl: config.apiBaseUrl, tokenValue: token, pathValue: requestPath, fileBase64: base64 })
}

async function expectApiOk(result, label) {
  expect(result.status, `${label}: ${JSON.stringify(result.json)}`).toBe(200)
  expect(result.json?.code, `${label}: ${JSON.stringify(result.json)}`).toBe(0)
  return result.json.data
}

async function captureViewport(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  const file = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path: file, contentType: 'image/png' })
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
  return { token: await login.token() }
}

test('AA-002 real XLSX roster import → Browser bulk registration → canonical readback', async ({ page }, testInfo) => {
  const facts = fixture()
  const { token } = await loginAcademicAdmin(page)
  const xlsxFile = path.join(repoRoot, facts.xlsxPath)
  expect(fs.existsSync(xlsxFile), `AA-002 XLSX missing: ${xlsxFile}`).toBeTruthy()

  const parsed = await expectApiOk(
    await browserUploadXlsx(page, token, '/academic-affairs/roster/import/xlsx', xlsxFile),
    'AA-002 real XLSX parse and dry-run'
  )
  expect(parsed.total).toBe(2)
  expect(parsed.validRows).toBe(2)
  expect(parsed.invalidRows).toBe(0)
  expect(parsed.passed).toBeTruthy()
  expect((parsed.rows || []).map((r) => r.studentNo)).toEqual(facts.rows.map((r) => r.studentNo))

  const imported = await expectApiOk(
    await browserApi(page, token, 'POST', '/academic-affairs/roster/import/confirm', { rows: parsed.rows }),
    'AA-002 confirm rows parsed from real XLSX'
  )
  expect(Number(imported.created || 0)).toBe(2)

  const rosterRows = []
  for (const fact of facts.rows) {
    const roster = await expectApiOk(
      await browserApi(page, token, 'GET', `/academic-affairs/roster?keyword=${encodeURIComponent(fact.studentNo)}&page=1&pageSize=20`),
      `AA-002 roster read ${fact.studentNo}`
    )
    const row = (roster.list || roster.items || []).find((item) => item.studentNo === fact.studentNo)
    expect(row, `AA-002 imported student missing from roster: ${fact.studentNo}`).toBeTruthy()
    expect(row.studentStatus).toBe('PENDING_REGISTER')
    rosterRows.push(row)
  }

  const suffix = String(Date.now()).slice(-8)
  const batch = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/registration-batches', {
    batchName: `AA-002真实XLSX注册-${suffix}`, registerType: 'ENROLL', open: true
  }), 'AA-002 create ENROLL batch')
  const candidates = await expectApiOk(await browserApi(
    page, token, 'GET', `/academic-affairs/registration-batches/${batch.batchId}/registration-candidates?page=1&pageSize=200`
  ), 'AA-002 read registration candidates')
  const expectedNos = new Set(facts.rows.map((r) => r.studentNo))
  const ready = (candidates.items || candidates.list || []).filter((item) => expectedNos.has(item.studentNo) && item.eligibilityStatus !== 'INELIGIBLE')
  expect(ready.length, JSON.stringify(candidates)).toBe(2)

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/registration/${batch.batchId}`)
  await dismissPageGuide(page)
  await expect(page.getByText('批量注册', { exact: true })).toBeVisible()
  for (const row of ready) {
    await expect(page.getByText(row.realName, { exact: true })).toBeVisible()
    await page.getByRole('checkbox', { name: `选择 ${row.realName || row.studentNo}` }).check()
  }
  await page.getByRole('button', { name: '预览批量注册' }).click()
  const preview = page.getByTestId('bulk-registration-preview')
  await expect(preview).toContainText('2 人可执行')
  await expect(preview).toContainText('0 人被阻断')
  await captureViewport(page, testInfo, 'aa002-registration-preview', 1440, 900)
  await page.getByLabel(/我已核对本次名单和阻断原因/).check()
  await page.getByRole('button', { name: '确认注册 2 人' }).click()
  const result = page.getByTestId('bulk-registration-result')
  await expect(result).toBeVisible({ timeout: 10000 })
  await expect(result).toContainText('成功 2 人')
  await expect(result).toContainText('未成功 0 人')

  const registrations = await expectApiOk(await browserApi(
    page, token, 'GET', `/academic-affairs/registration-batches/${batch.batchId}/registrations?page=1&pageSize=50`
  ), 'AA-002 canonical registration readback')
  const registered = (registrations.items || registrations.list || []).filter((item) => expectedNos.has(item.studentNo))
  expect(registered.length).toBe(2)

  fs.writeFileSync(outcomePath, JSON.stringify({
    productSha: process.env.E2E_EXPECTED_SHA || '', xlsxUploadPass: true, xlsxParsedRows: parsed.rows,
    imported, batchId: String(batch.batchId), batchName: batch.batchName,
    students: ready.map((r) => ({ studentId: String(r.studentId), studentNo: r.studentNo, realName: r.realName })),
    registrationIds: registered.map((r) => String(r.registrationId)), browserPass: true
  }, null, 2), 'utf8')
})
