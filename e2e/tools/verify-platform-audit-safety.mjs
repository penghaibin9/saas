/** DOM regression only: no authentication fixture and no live or irreversible action. */
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js'
const root = fileURLToPath(new URL('../../', import.meta.url))
const out = path.join(root, 'artifacts/platform-workspace/audited-ui')
const report = { realVue: true, liveBackend: false, credentialsUsed: false, irreversibleOperations: false, checks: [], pageErrors: [], apiRequests: [] }
await fs.mkdir(out, { recursive: true })
let server, browser, page
async function check(name, fn) {
  try { await fn(); report.checks.push({ name, passed: true }) }
  catch (error) { report.checks.push({ name, passed: false, error: String(error) }); await page?.screenshot({path:path.join(out, `failure-${report.checks.length}.png`),fullPage:true}) }
}
async function open(panel, mode = 'normal') {
  await page.goto(`http://127.0.0.1:5179/tests/visual/platform-audit-safety.html?panel=${panel}&case=${mode}`, { waitUntil: 'networkidle' })
}
const writes = () => page.evaluate(() => window.__auditSafety.calls)
try {
  server = await createServer({ root: path.join(root, 'frontend'), configFile: path.join(root, 'frontend/vite.config.js'), server: {host:'127.0.0.1', port:5179, strictPort:true, open:false} })
  await server.listen(); browser = await chromium.launch({ headless:true }); page = await browser.newPage({ viewport:{width:1366,height:950} })
  page.on('pageerror', error => report.pageErrors.push(String(error)))
  page.on('dialog', dialog => dialog.accept())
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {report.apiRequests.push(route.request().url()); return route.abort()})
  await check('portal failed read has retry but no editable defaults or save', async () => {
    await open('portal','read-error')
    await expect(page.getByRole('alert')).toContainText('未载入可保存的默认值')
    await expect(page.getByRole('button',{name:'重新读取配置',exact:true})).toBeVisible()
    await expect(page.getByRole('button',{name:'保存配置',exact:true})).toHaveCount(0)
    await expect(page.locator('fieldset')).toHaveCount(0); assert.equal((await writes()).length,0)
  })
  await check('malformed portal response cannot unlock editing', async () => {
    await open('portal','malformed'); await expect(page.getByRole('alert')).toContainText('未载入可保存的默认值'); await expect(page.locator('fieldset')).toHaveCount(0)
  })
  await check('portal saves exactly one draft and displays accepted server switches', async () => {
    await open('portal'); await expect(page.getByRole('button',{name:'保存配置',exact:true})).toBeDisabled()
    await page.getByLabel('门户名称',{exact:true}).fill('修改后的学校门户')
    await page.getByLabel('智能助手',{exact:true}).check()
    await page.getByRole('button',{name:'保存配置',exact:true}).click()
    await expect(page.getByRole('status')).toContainText('服务器返回值')
    await expect(page.getByLabel('智能助手',{exact:true})).not.toBeChecked()
    await expect(page.getByRole('button',{name:'保存配置',exact:true})).toBeDisabled()
    assert.equal((await writes()).length,1)
    await page.screenshot({path:path.join(out,'portal-saved.png'),fullPage:true})
  })
  await check('portal restore defaults remains unsaved until explicit save', async () => {
    await open('portal'); await page.getByRole('button',{name:'恢复默认',exact:true}).click()
    await expect(page.getByRole('status')).toContainText('未保存'); assert.equal((await writes()).length,0)
  })
  await check('unconfirmed portal save locks form and readback cannot replay it', async () => {
    await open('portal','save-error'); await page.getByLabel('门户名称',{exact:true}).fill('草稿学校名')
    await page.getByRole('button',{name:'保存配置',exact:true}).click()
    await expect(page.locator('fieldset')).toBeDisabled()
    await page.getByRole('button',{name:'只读取当前配置',exact:true}).click()
    await expect(page.locator('fieldset')).toBeDisabled(); assert.equal((await writes()).length,1)
    await page.getByRole('button',{name:'已核对，结束本次记录',exact:true}).click()
    await expect(page.locator('fieldset')).toBeEnabled()
  })
  await check('school switch clears portal draft instead of copying to another school', async () => {
    await open('portal'); await page.getByLabel('门户名称',{exact:true}).fill('学校甲草稿')
    await page.getByRole('button',{name:'测试切换学校',exact:true}).click()
    await expect(page.getByLabel('门户名称',{exact:true})).toHaveValue('学校门户'); assert.equal((await writes()).length,0)
  })
  await check('missing legal-hold evidence remains a blocking warning and no purge action', async () => {
    await open('exit','missing-hold')
    await expect(page.locator('.top__gates')).toContainText('证据未取得，禁止销毁')
    await expect(page.getByRole('button',{name:'永久销毁租户数据',exact:true})).toHaveCount(0)
    assert.equal((await writes()).length,0)
    await page.screenshot({path:path.join(out,'offboarding-missing-evidence.png'),fullPage:true})
  })
  await check('offboarding read failure exposes retry without stale task actions', async () => {
    await open('exit','read-error'); await expect(page.locator('.top')).toContainText('证据未取得')
    await expect(page.getByRole('button',{name:'发起退租并冻结只读',exact:true})).toHaveCount(0)
  })
  await check('reversible request and cancel display state transitions in the real component', async () => {
    await open('exit'); await page.locator('textarea').fill('隔离验证学校申请终止服务核验流程')
    await page.getByRole('button',{name:'发起退租并冻结只读',exact:true}).click()
    await expect(page.locator('.top__job-grid')).toContainText('已冻结只读')
    await page.getByPlaceholder('取消原因（至少 5 个字符）').fill('核验结束继续使用')
    await page.getByRole('button',{name:'取消退租',exact:true}).click()
    await expect(page.getByRole('button',{name:'发起退租并冻结只读',exact:true})).toBeVisible()
    assert.deepEqual((await writes()).map(item=>item.operation),['offboard-request','offboard-cancel'])
  })
  await check('unconfirmed offboarding request cannot repeat from the same record', async () => {
    await open('exit','save-error'); await page.locator('textarea').fill('隔离验证学校申请终止服务核验流程')
    await page.getByRole('button',{name:'发起退租并冻结只读',exact:true}).click()
    await expect(page.getByRole('button',{name:'发起退租并冻结只读',exact:true})).toBeDisabled()
    await page.getByRole('button',{name:'只读取当前状态',exact:true}).click()
    await expect(page.getByRole('button',{name:'发起退租并冻结只读',exact:true})).toBeDisabled()
    assert.equal((await writes()).length,1)
  })
  await check('no runtime exceptions and no API calls left the isolated view', async () => {assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.apiRequests,[])})
} finally {
  report.passed = report.checks.length > 0 && report.checks.every(item=>item.passed)
  await fs.writeFile(path.join(out,'report.json'),JSON.stringify(report,null,2))
  await browser?.close(); await server?.close(); console.log(JSON.stringify(report,null,2))
  if (!report.passed) process.exitCode = 1
}
