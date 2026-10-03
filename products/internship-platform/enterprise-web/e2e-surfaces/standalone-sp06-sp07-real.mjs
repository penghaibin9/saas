import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE_PATH ? pathToFileURL(process.env.PLAYWRIGHT_MODULE_PATH).href : 'playwright')
const out = process.env.SP06_EVIDENCE_DIR
assert(out, 'SP06_EVIDENCE_DIR is required')
const { fixture: s } = JSON.parse(await fs.readFile(path.join(out, 'seed.json'), 'utf8'))
const studentUrl = process.env.SP06_STUDENT_URL || 'http://127.0.0.1:5277'
const adminUrl = process.env.SP06_ADMIN_URL || 'http://127.0.0.1:5276'
for (const url of [studentUrl, adminUrl]) assert.equal(new URL(url).hostname, '127.0.0.1')
const seen = [], errors = [], results = []
const browser = await chromium.launch({ headless: true, channel: 'msedge' })
const student = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const admin = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
for (const page of [student, admin]) {
  page.on('response', r => { const u = new URL(r.url()); if (u.pathname.startsWith('/api/v1/')) seen.push({ path: u.pathname, status: r.status() }) })
  page.on('pageerror', e => errors.push(e.message))
}
async function evaluationPage() {
  const group = student.locator('details.sp-process-group').filter({ hasText: '变更与结果' })
  if (await group.getAttribute('open') === null) await group.locator('summary').click()
  await student.getByRole('button', { name: '实习成绩/自评', exact: true }).click()
  await student.locator('.sp-formal-docs').waitFor({ state: 'visible' })
}
async function studentGenerate(title, filename, reused) {
  const card = student.locator('.sp-formal-docs__grid > div').filter({ hasText: title })
  const downloadPromise = student.waitForEvent('download', { timeout: 30000 })
  const responsePromise = student.waitForResponse(r => r.url().includes('/formal-documents/generate') && r.request().method() === 'POST')
  await card.getByRole('button', { name: '生成最新 PDF', exact: true }).click()
  const response = await responsePromise
  const body = await response.json()
  assert.equal(body.code, 0, JSON.stringify(body))
  assert.equal(Boolean(body.data.reused), reused)
  const download = await downloadPromise
  assert.equal(await download.failure(), null)
  await download.saveAs(path.join(out, filename))
  results.push({ action: title, reused, id: body.data.id, version: body.data.documentVersion })
  return body.data
}
try {
  await student.goto(studentUrl + '/student/login')
  await student.getByLabel('学校编码').fill('AUTH-GATE')
  await student.getByLabel('学号 / 登录账号').fill(s.login)
  await student.getByLabel('密码').fill('Gap09-Isolated-Student-2026!')
  await student.getByRole('button', { name: '登录', exact: true }).click()
  await student.waitForURL(/\/student\/internship/)
  await evaluationPage()
  await student.screenshot({ path: path.join(out, 'student-before.png'), fullPage: true })
  const appraisal = await studentGenerate('企业实习鉴定表', 'student-appraisal.pdf', false)
  await studentGenerate('学生实习证明', 'student-certificate.pdf', false)
  await student.reload()
  await evaluationPage()
  const again = await studentGenerate('企业实习鉴定表', 'student-appraisal-reused.pdf', true)
  assert.equal(again.id, appraisal.id)
  await student.screenshot({ path: path.join(out, 'student-after-refresh.png'), fullPage: true })
  await admin.goto(adminUrl + '/login')
  await admin.getByLabel('学校编码').fill('AUTH-GATE')
  assert.equal(errors.length, 0, JSON.stringify(errors))
  assert(!seen.some(x => x.status >= 500), JSON.stringify(seen.filter(x => x.status >= 500)))
  const evidence = { status: 'PASS', scope: 'Student PC SP06/SP07', adminBrowser: 'NOT_RUN', results, seen, errors }
  await fs.writeFile(path.join(out, 'browser-result.json'), JSON.stringify(evidence, null, 2))
  console.log(JSON.stringify({ status: 'PASS', results }))
} catch (error) {
  await student.screenshot({ path: path.join(out, 'student-failure.png'), fullPage: true }).catch(() => {})
  await fs.writeFile(path.join(out, 'browser-result.json'), JSON.stringify({ status: 'FAIL', message: error.message, results, seen, errors, studentText: await student.locator('body').innerText() }, null, 2))
  throw error
} finally { await browser.close() }
