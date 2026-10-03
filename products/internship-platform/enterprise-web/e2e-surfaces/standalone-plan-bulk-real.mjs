import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE_PATH ? pathToFileURL(process.env.PLAYWRIGHT_MODULE_PATH).href : 'playwright')
const out = process.env.BULK_EVIDENCE_DIR
assert(out, 'BULK_EVIDENCE_DIR required')
const seed = JSON.parse(await fs.readFile(path.join(out, 'seed.json'), 'utf8'))
const base = process.env.BULK_ADMIN_URL || 'http://127.0.0.1:5285'
assert.equal(new URL(base).hostname, '127.0.0.1')
const browser = await chromium.launch({ headless: true, channel: process.env.BULK_BROWSER_CHANNEL || 'msedge' })
const pages = [], results = [], failures = [], pageErrors = [], deviceMatrix = []
async function login(role) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage(); pages.push(page)
  page.on('pageerror', e => pageErrors.push(e.message))
  page.on('response', r => {
    const u = new URL(r.url()); if (u.pathname.startsWith('/api/v1/') && r.status() >= 400 && !u.pathname.endsWith('/browser-refresh')) failures.push({ role, path: u.pathname, status: r.status() })
  })
  await page.goto(base+'/login')
  await page.getByLabel('学校编码').fill(seed.tenantCode)
  await page.getByLabel('账号').fill(role.toLowerCase())
  await page.getByLabel('密码').fill('Bulk-Tests-Only-2026!')
  await page.getByRole('button',{ name:'登录',exact:true }).click()
  await page.waitForURL(/\/admin\/internship/, { timeout:30000 })
  await page.goto(base+'/admin/internship/plans?batchId='+seed.batches[0].id)
  await page.getByRole('button',{ name:'批量导出计划',exact:true }).click()
  await page.locator('.plan-bulk table, .plan-bulk p').first().waitFor()
  return page
}
async function exportFromPage(page, format, filename, count) {
  const responsePromise = page.waitForResponse(r => r.url().includes('/plans/bulk-export.'+format) && r.request().method() === 'POST')
  const downloadPromise = page.waitForEvent('download', { timeout:30000 })
  await page.getByRole('button',{ name:format === 'pdf' ? '批量导出 PDF':'批量导出 Excel',exact:true }).click()
  const response = await responsePromise, data = await response.json()
  assert.equal(response.status(),200,JSON.stringify(data)); assert.equal(data.code,0,JSON.stringify(data))
  const ids = response.request().postDataJSON().batchIds
  assert.equal(ids.length,count); assert(ids.every(id => typeof id === 'string'))
  const download = await downloadPromise; assert.equal(await download.failure(),null)
  await download.saveAs(path.join(out,filename))
  const bytes = await fs.readFile(path.join(out,filename))
  assert.deepEqual(bytes,Buffer.from(data.data.contentBase64,'base64'))
  assert(bytes.subarray(0,format === 'pdf' ? 4:2).equals(Buffer.from(format === 'pdf' ? '%PDF':'PK')))
  results.push({ action:filename, ids, count, bytes:bytes.length })
  return bytes
}
try {
  const admin = await login('SCHOOL_ADMIN')
  const rows = admin.locator('.plan-bulk tbody tr')
  await rows.nth(19).waitFor(); assert.equal(await rows.count(),20)
  await rows.first().getByRole('checkbox').check()
  const next = admin.waitForResponse(r => r.url().includes('/plans/export-options') && new URL(r.url()).searchParams.get('page') === '2')
  await admin.getByRole('button',{ name:'下一页计划',exact:true }).click(); await next
  await rows.nth(2).waitFor(); assert.equal(await rows.count(),3)
  await rows.first().getByRole('checkbox').check()
  await admin.getByText('查看已选 2 份计划（检索、翻页不会清空）',{ exact:true }).waitFor()
  await exportFromPage(admin,'pdf','admin-two-plans.pdf',2)
  await exportFromPage(admin,'xlsx','admin-two-plans.xlsx',2)
  await admin.locator('.plan-bulk').screenshot({ path:path.join(out,'admin-after-export.png') })
  // Failure-only injection; all success paths above and below use real API responses.
  await admin.route('**/api/v1/internship/plans/bulk-export.xlsx', route => route.abort('connectionfailed'))
  await admin.getByRole('button',{ name:'批量导出 Excel',exact:true }).click()
  await admin.locator('.plan-bulk__error').waitFor({ state:'visible' })
  await admin.getByText('查看已选 2 份计划（检索、翻页不会清空）',{ exact:true }).waitFor()
  await admin.locator('.plan-bulk').screenshot({ path:path.join(out,'admin-failure-keeps-selection.png') })
  await admin.unroute('**/api/v1/internship/plans/bulk-export.xlsx')
  await exportFromPage(admin,'xlsx','admin-retry.xlsx',2)
  results.push({ action:'network-failure-retry', selectionRetained:true })
  await admin.setViewportSize({ width:390,height:844 })
  const bounds = await admin.locator('.plan-bulk').boundingBox()
  deviceMatrix.push({ width:390, passed:bounds.x >= -1 && bounds.x+bounds.width <= 391, bodyMinWidth:await admin.evaluate(() => getComputedStyle(document.body).minWidth), scope:'PC shell narrow-screen diagnostic' })
  await admin.locator('.plan-bulk').screenshot({ path:path.join(out,'admin-390px.png') })
  await admin.setViewportSize({ width:1180,height:1000 })
  const pcBounds = await admin.locator('.plan-bulk').boundingBox()
  assert(pcBounds.x >= -1 && pcBounds.x+pcBounds.width <= 1181,'Bulk panel exceeds supported PC width')
  deviceMatrix.push({ width:1180, passed:true, scope:'PC acceptance' })
  await admin.locator('.plan-bulk').screenshot({ path:path.join(out,'admin-1180px.png') })
  await admin.setViewportSize({ width:1440,height:1000 })
  await admin.reload()
  await admin.getByRole('button',{ name:'批量导出计划',exact:true }).click()
  await admin.locator('.plan-bulk tbody tr').first().waitFor()
  assert.equal(await admin.locator('.plan-bulk tbody input:checked').count(),0)
  results.push({ action:'refresh', previousSelectionNotPersisted:true })
  const teacher = await login('INTERN_MENTOR')
  await teacher.getByLabel('计划名称、编号或批次').fill(seed.batches[0].planNo)
  const search = teacher.waitForResponse(r => r.url().includes('/plans/export-options') && r.url().includes('keyword='))
  await teacher.getByRole('button',{ name:'检索计划',exact:true }).click(); await search
  await teacher.locator('.plan-bulk tbody tr').first().waitFor()
  assert.equal(await teacher.locator('.plan-bulk tbody tr').count(),1)
  await teacher.locator('.plan-bulk tbody input').check()
  await exportFromPage(teacher,'pdf','teacher-own-plan.pdf',1)
  await teacher.locator('.plan-bulk').screenshot({ path:path.join(out,'teacher-scoped-export.png') })
  assert.equal(failures.length,0,JSON.stringify(failures))
  assert.equal(pageErrors.length,0,JSON.stringify(pageErrors))
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({ status:deviceMatrix.every(x => x.passed) ? 'PASS':'PARTIAL', pcFlow:'PASS', results,failures,pageErrors,deviceMatrix },null,2))
  console.log(JSON.stringify({ pcFlow:'PASS',actions:results.length,deviceMatrix }))
} catch(error) {
  for (const [index,page] of pages.entries()) {
    await page.screenshot({ path:path.join(out,`failure-${index}.png`),fullPage:true }).catch(() => {})
    await fs.writeFile(path.join(out,`failure-${index}.txt`),await page.locator('body').innerText()).catch(() => {})
  }
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({ status:'FAIL',message:error.message,results,failures,pageErrors },null,2))
  throw error
} finally { await browser.close() }
