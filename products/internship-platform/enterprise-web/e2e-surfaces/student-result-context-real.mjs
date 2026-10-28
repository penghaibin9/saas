import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE_PATH ? pathToFileURL(process.env.PLAYWRIGHT_MODULE_PATH).href : 'playwright')
const out = process.env.SP06_EVIDENCE_DIR
const { fixture: s } = JSON.parse(await fs.readFile(path.join(out,'seed.json'),'utf8'))
const base = process.env.SP06_STUDENT_URL || 'http://127.0.0.1:5287'
assert.equal(new URL(base).hostname,'127.0.0.1')
const browser = await chromium.launch({ headless:true,channel:'msedge' })
const page = await browser.newPage({ viewport:{ width:1440,height:1000 } })
const requests = [], errors = [], exports = []
const required = ['/portal/internship/insurance','/portal/internship/context/weekly-reports',
  '/portal/internship/context/reports','/portal/internship/context/self-eval','/portal/internship/score/appeal']
page.on('response',r => { const p = new URL(r.url()).pathname; if (p.startsWith('/api/v1/')) requests.push({ path:p,status:r.status() }) })
page.on('pageerror',e => errors.push(e.message))
async function openResults() {
  const group = page.locator('details.sp-process-group').filter({ hasText:'变更与结果' })
  if (await group.getAttribute('open') === null) await group.locator('summary').click()
  await page.getByRole('button',{ name:'实习成绩/自评',exact:true }).click()
  await page.locator('.sp-formal-docs').waitFor({ state:'visible' })
}
async function generate(title, filename) {
  const card = page.locator('.sp-formal-docs__grid > div').filter({ hasText:title })
  const responsePromise = page.waitForResponse(r => r.url().includes('/formal-documents/generate') && r.request().method() === 'POST')
  const downloadPromise = page.waitForEvent('download')
  await card.getByRole('button',{ name:'生成最新 PDF',exact:true }).click()
  const response = await responsePromise, body = await response.json()
  assert.equal(body.code,0,JSON.stringify(body))
  const download = await downloadPromise; assert.equal(await download.failure(),null)
  await download.saveAs(path.join(out,filename))
  assert((await fs.readFile(path.join(out,filename))).subarray(0,4).equals(Buffer.from('%PDF')))
  exports.push({ documentType:body.data.documentType,id:body.data.id,reused:body.data.reused })
}
try {
  const reads = required.map(p => page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1'+p,{ timeout:45000 }))
  await page.goto(base+'/student/login')
  await page.getByLabel('学校编码').fill('AUTH-GATE')
  await page.getByLabel('学号 / 登录账号').fill(s.login)
  await page.getByLabel('密码').fill('Gap09-Isolated-Student-2026!')
  await page.getByRole('button',{ name:'登录',exact:true }).click()
  await page.waitForURL(/\/student\/internship/)
  await openResults()
  for (const response of await Promise.all(reads)) {
    assert.equal(response.status(),200,await response.text())
    assert.equal((await response.json()).code,0)
  }
  await generate('企业实习鉴定表','context-appraisal.pdf')
  await generate('学生实习证明','context-certificate.pdf')
  await page.reload(); await openResults()
  await generate('企业实习鉴定表','context-appraisal-reused.pdf')
  assert.equal(exports[2].id,exports[0].id); assert.equal(exports[2].reused,true)
  assert.equal(await page.locator('.sp-source-state--error').count(),0,'Result page retains a business error banner')
  const failures = requests.filter(r => r.status >= 400 && !r.path.endsWith('/browser-refresh'))
  assert.deepEqual(failures,[]); assert.deepEqual(errors,[])
  await page.screenshot({ path:path.join(out,'student-result-clean.png'),fullPage:true })
  await fs.writeFile(path.join(out,'context-result.json'),JSON.stringify({ status:'PASS',required,requests,errors,exports },null,2))
  console.log('STUDENT_RESULT_CONTEXT_AND_DOWNLOAD_PASS')
} catch(error) {
  await page.screenshot({ path:path.join(out,'student-context-failed.png'),fullPage:true }).catch(() => {})
  await fs.writeFile(path.join(out,'context-result.json'),JSON.stringify({ status:'FAIL',message:error.message,requests,errors,exports },null,2))
  throw error
} finally { await browser.close() }
