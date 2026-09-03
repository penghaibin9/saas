import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { promisify } from 'node:util'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const ROUTE = '/admin/student-affairs/dashboard'
const DASHBOARD_API = /\/api\/v1\/student-affairs\/dashboard(?:\?|$)/
const EXPORT_API = /\/api\/v1\/export\/students(?:\?|$)/
const EXPORT_PURPOSE = '学工看板范围学生台账导出'
const execFileAsync = promisify(execFile)
const countLabel = (value) => {
  if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+$/.test(value))) return '—'
  const count = Number(value)
  return Number.isSafeInteger(count) && count >= 0 ? new Intl.NumberFormat('zh-CN').format(count) : '—'
}
async function open(page) {
  await page.setViewportSize({ width: 1366, height: 768 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    if (await page.locator(selector).isVisible().catch(() => false)) {
      await page.getByRole('button', { name: /跳过引导|跳过/ }).first().click()
      await expect(page.locator(selector)).toBeHidden()
    }
  }
}
async function capture(page, testInfo, label) {
  const target = testInfo.outputPath(`${label}.png`)
  await page.screenshot({ path: target, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(label, { path: target, contentType: 'image/png' })
}

test('V6 A1 refresh click renders the newly returned real aggregate', async ({ page }, testInfo) => {
  await open(page)
  const refresh = page.getByRole('button', { name: '刷新', exact: true })
  await expect(refresh).toBeEnabled()
  const responsePromise = page.waitForResponse((res) => DASHBOARD_API.test(res.url()) && res.request().method() === 'GET')
  await refresh.click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const envelope = await response.json()
  expect(envelope.code).toBe(0)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  for (const key of ['pendingTodo', 'pendingLeave', 'overdueLeave', 'riskStudents']) {
    const metric = envelope.data.summaryCards.find((item) => item.key === key)
    await expect(page.locator(`[data-metric="${key}"] dd`)).toHaveText(countLabel(metric?.value))
  }
  await expect(refresh).toBeEnabled()
  await expect.poll(() => new URL(page.url()).pathname).toBe(ROUTE)
  await capture(page, testInfo, 'v6-a1-refresh-real-api')
})

test('V6 A1 error retry restores real data through a browser click', async ({ page }, testInfo) => {
  await open(page)
  // Intercept one response only; the recovery must use the actual backend.
  await page.route(DASHBOARD_API, (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data: null })
  }), { times: 1 })
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page.locator('.sa-v6-dashboard')).toHaveCount(0)
  await expect(page.locator('.sa-v6-page-shell')).toContainText('未取得有效的学工汇总')
  await capture(page, testInfo, 'v6-a1-retry-before')
  const responsePromise = page.waitForResponse((res) => DASHBOARD_API.test(res.url()) && res.request().method() === 'GET')
  // Exercise the error panel's actual recovery control, not the toolbar refresh.
  const retry = page.locator('.ags-error').getByRole('button', { name: '重试', exact: true })
  await expect(retry).toBeVisible()
  await expect(retry).toBeEnabled()
  await retry.click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect((await response.json()).code).toBe(0)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  await expect(page.locator('.sa-v6-queue-row')).toHaveCount(7)
  await capture(page, testInfo, 'v6-a1-retry-real-recovery')
})

test('V6 A1 export click completes authenticated xlsx download', async ({ page }, testInfo) => {
  test.setTimeout(90_000)
  await open(page)
  const button = page.getByRole('button', { name: '导出 Excel 台账', exact: true })
  await expect(button).toBeEnabled()
  const responsePromise = page.waitForResponse((res) => EXPORT_API.test(res.url()) && res.request().method() === 'POST')
  const fileResponsePromise = page.waitForResponse((res) => /\/api\/v1\/export\/tasks\/[^/]+\/download(?:\?|$)/.test(res.url()) && res.request().method() === 'GET')
  const downloadPromise = page.waitForEvent('download')
  await button.click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON()).toEqual({ purpose: EXPORT_PURPOSE })
  const envelope = await response.json()
  expect(envelope.code).toBe(0)
  expect(envelope.data.taskId).toEqual(expect.any(String))
  expect(envelope.data.purpose).toBe(EXPORT_PURPOSE)
  // The wire response is an ExportTask; the frontend adapter builds its download URL.
  expect(envelope.data.status).toBe('SUCCESS')
  expect(envelope.data.taskId).toMatch(/^\d+$/)
  expect(envelope.data.fileName).toMatch(/\.xlsx$/i)
  expect(Number.isSafeInteger(envelope.data.rowCount)).toBe(true)
  expect(envelope.data.rowCount).toBeGreaterThanOrEqual(0)
  const fileResponse = await fileResponsePromise
  expect(fileResponse.status()).toBe(200)
  expect(new URL(fileResponse.url()).pathname).toContain(`/export/tasks/${envelope.data.taskId}/download`)
  expect(fileResponse.headers()['content-type']).toContain('spreadsheetml.sheet')
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(envelope.data.fileName)
  expect(await download.failure()).toBeNull()
  const temporary = await mkdtemp(path.join(tmpdir(), 'a1-xlsx-'))
  try {
    const file = path.join(temporary, 'ledger.xlsx')
    await download.saveAs(file)
    const bytes = await readFile(file)
    assert.ok(bytes.length > 100, 'Downloaded xlsx must not be an empty response')
    assert.equal(bytes.subarray(0, 4).toString('hex'), '504b0304', 'Downloaded file must be an actual ZIP container')
    // Validate the workbook, without printing/exporting student rows into test evidence.
    const { stdout } = await execFileAsync('python', ['-c', [
      'import json, sys, zipfile',
      'from xml.etree import ElementTree as ET',
      'with zipfile.ZipFile(sys.argv[1]) as z:',
      '    assert z.testzip() is None, "Corrupt xlsx archive"',
      '    names = z.namelist()',
      '    assert "[Content_Types].xml" in names and "xl/workbook.xml" in names',
      '    sheets = [n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]',
      '    assert sheets, "No worksheet in export"',
      '    ET.fromstring(z.read("xl/workbook.xml"))',
      '    for sheet in sheets: ET.fromstring(z.read(sheet))',
      '    print(json.dumps({"validXlsx": True, "worksheetCount": len(sheets)}))'
    ].join('\n'), file], { timeout: 15_000, maxBuffer: 4096 })
    const validation = JSON.parse(stdout)
    expect(validation.validXlsx).toBe(true)
    await testInfo.attach('v6-a1-export-verification', {
      body: JSON.stringify({ ...validation, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex'),
        requestPurposeMatched: true, authenticatedDownload: true }, null, 2),
      contentType: 'application/json'
    })
  } finally {
    await rm(temporary, { recursive: true, force: true })
    await download.delete()
  }
  await expect(button).toBeEnabled()
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  await capture(page, testInfo, 'v6-a1-export-completed')
})

test('V6 A1 audit degradation recovers with a real refresh click', async ({ page }, testInfo) => {
  await open(page)
  const audit = page.locator('.sa-dashboard-panel--audit')
  await expect(audit).not.toContainText('正在读取操作记录')
  const auditApi = /\/api\/v1\/audit\/logs(?:\?|$)/
  // Isolate a single failure; the second refresh must retrieve the real audit endpoint.
  await page.route(auditApi, (route) => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ code: 503001, message: 'E2E audit unavailable' })
  }), { times: 1 })
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(audit).toContainText('操作记录暂不可用')
  await expect(audit).not.toContainText('暂无可展示审计记录')
  await expect(page.locator('.sa-v6-queue-row')).toHaveCount(7)
  await capture(page, testInfo, 'v6-a1-audit-recovery-before')
  const responsePromise = page.waitForResponse((res) => auditApi.test(res.url()) && res.request().method() === 'GET')
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect((await response.json()).code).toBe(0)
  await expect(audit).not.toContainText('操作记录暂不可用')
  await expect(audit).not.toContainText('正在读取操作记录')
  await expect(page.locator('.sa-v6-queue-row')).toHaveCount(7)
  await capture(page, testInfo, 'v6-a1-audit-recovery-real-api')
})
