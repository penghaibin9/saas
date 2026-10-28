import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { spawn, spawnSync } from 'node:child_process'
import assert from 'node:assert/strict'

assert.equal(process.env.APP_ENV, 'test')
assert.equal(process.env.GAP09_MYSQL_ACCEPTANCE, '1')
const origin = process.env.SCAN_STUDENT_ORIGIN
assert.equal(new URL(origin).hostname, '127.0.0.1')
const out = process.env.WRITE_EVIDENCE_DIR
const flow = JSON.parse(await fs.readFile(path.join(out, 'flow.json'), 'utf8'))
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE_PATH
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE_PATH).href : 'playwright')
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 },
  locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
const failures = [], errors = [], receipts = []
const unauthenticatedStartup = []
let signedIn = false
page.on('pageerror', error => errors.push(error.message))
page.on('response', response => {
  const pathname = new URL(response.url()).pathname
  if (!signedIn && pathname === '/api/v1/auth/browser-refresh' && response.status() === 401) {
    unauthenticatedStartup.push({ path: pathname, status: 401 })
    return
  }
  if (response.url().includes('/api/v1/') && response.status() >= 400)
    failures.push({ path: new URL(response.url()).pathname, status: response.status() })
})
let worker
const heartbeat = path.join(out, 'scan-worker-heartbeat.json')
async function startWorker() {
  if (worker) return
  worker = spawn(process.env.SCAN_WORKER_PYTHON, ['-m', 'app.file_scan_worker', '--interval', '0.2', '--heartbeat-file', heartbeat],
    { env: { ...process.env, CLAMAV_ENABLED: 'true', FILE_SCAN_REQUIRED: 'true' }, stdio: 'ignore' })
}
async function tab(groupName, name) {
  const group = page.locator('details.sp-process-group').filter({ hasText: groupName })
  if (await group.getAttribute('open') === null) await group.locator('summary').click()
  await group.getByRole('button', { name, exact: true }).click()
}
async function upload(input, file) {
  const pending = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/files')
  await input.setInputFiles(file)
  const response = await pending
  const payload = await response.json()
  assert.equal(response.status(), 200)
  assert.equal(payload.code, 0)
  assert.equal(payload.data.status, 'QUARANTINED')
  assert.equal(payload.data.readyForBusiness, false)
  return payload.data
}
async function post(button, endpoint) {
  const pending = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === endpoint)
  await button.click()
  const response = await pending, payload = await response.json()
  assert.equal(response.status(), 200)
  assert.equal(payload.code, 0, JSON.stringify(payload))
  receipts.push({ path: endpoint, id: payload.data.id })
}
async function refreshUntilReady(button, submit) {
  for (let i = 0; i < 40 && !await submit.isEnabled(); i++) {
    if (await button.isEnabled()) await button.click()
    await page.waitForFunction(() => !document.querySelector('.sp-btn:disabled')?.textContent?.includes('处理中'), { timeout: 5000 })
    if (!await submit.isEnabled()) await new Promise(resolve => setTimeout(resolve, 200))
  }
  assert.equal(await submit.isEnabled(), true, 'clean scan must unlock the original draft')
}
try {
  await page.goto(origin + '/student/login')
  await page.getByLabel('学校编码').fill(flow.tenantCode)
  await page.getByLabel('学号 / 登录账号', { exact: true }).fill('student')
  await page.getByLabel('密码', { exact: true }).fill('Bulk-Tests-Only-2026!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.waitForURL(/\/student\/internship/)
  signedIn = true
  await tab('安排与入岗', '实习保险')
  await page.getByLabel('保单号', { exact: true }).fill('SCAN-' + flow.batchId)
  await page.getByLabel('承保机构', { exact: true }).fill('合成验收保险机构')
  await page.getByLabel('险种', { exact: true }).fill('实习责任保险')
  await page.getByLabel('生效日期', { exact: true }).fill('2026-09-01')
  await page.getByLabel('到期日期', { exact: true }).fill('2026-12-31')
  const cleanPdf = path.join(out, 'clean-policy.pdf')
  await fs.access(cleanPdf)
  const file = await upload(page.locator('input[type=file]'), cleanPdf)
  const submit = page.getByRole('button', { name: '提交保险', exact: true })
  await page.getByText('clean-policy.pdf · 等待安全扫描', { exact: true }).waitFor()
  assert.equal(await submit.isEnabled(), false)
  await page.screenshot({ path: path.join(out, 'insurance-scan-pending.png'), fullPage: true })
  await startWorker()
  await refreshUntilReady(page.getByRole('button', { name: '查看保单扫描结果', exact: true }), submit)
  assert.equal(await page.getByLabel('保单号', { exact: true }).inputValue(), 'SCAN-' + flow.batchId)
  await post(submit, '/api/v1/portal/internship/insurance')
  await page.reload()
  await tab('安排与入岗', '实习保险')
  await page.getByText('状态：待核验', { exact: true }).waitFor()
  await page.screenshot({ path: path.join(out, 'insurance-scanned-submitted.png'), fullPage: true })
  await tab('在岗办理', '周报/月报/总结')
  await page.getByRole('button', { name: '月报', exact: true }).click()
  const editor = page.locator('.report-editor')
  const body = '记录真实岗位实习工作过程与成果，并完成老师要求的学习内容。'.repeat(12)
  await editor.locator('input[type=month]').fill('2026-09')
  await editor.locator('textarea').fill(body)
  await upload(editor.locator('input[type=file]'), cleanPdf)
  const reportSubmit = editor.getByRole('button', { name: '提交月报', exact: true })
  await refreshUntilReady(page.getByRole('button', { name: '查看报告附件扫描结果', exact: true }), reportSubmit)
  assert.equal(await editor.locator('textarea').inputValue(), body)
  await post(reportSubmit, '/api/v1/portal/internship/context/reports')
  await page.reload()
  await tab('在岗办理', '周报/月报/总结')
  await page.getByRole('button', { name: '月报', exact: true }).click()
  await page.getByText('clean-policy.pdf', { exact: true }).waitFor()
  await page.screenshot({ path: path.join(out, 'report-scanned-submitted.png'), fullPage: true })
  const probe = spawnSync(process.env.SCAN_WORKER_PYTHON,
    ['-m', 'app.file_scan_worker', '--healthcheck', '--heartbeat-file', heartbeat],
    { env: process.env, timeout: 10000, encoding: 'utf8' })
  assert.equal(probe.status, 0, 'live worker heartbeat must pass the deployment health probe')
  assert.deepEqual(errors, [])
  assert.deepEqual(failures, [])
  await fs.writeFile(path.join(out, 'scan-browser.json'), JSON.stringify({ status: 'PASS',
    receipts, errors, failures, unauthenticatedStartup, insuranceFileId: file.fileId,
    realWorker: true, workerHealthcheck: 'PASS' }, null, 2))
  console.log('Real browser: quarantine → scanner → original insurance/report submission → reload PASS')
} finally {
  if (worker) worker.kill('SIGTERM')
  await browser.close()
}
