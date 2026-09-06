/** Real Vue rendering with isolated fixtures; not a live-backend acceptance substitute. */
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js'

const root = fileURLToPath(new URL('../../', import.meta.url))
const out = path.join(root, 'artifacts/platform-workspace/visual')
await fs.mkdir(out, { recursive: true })
const report = { realVue: true, isolatedFixtures: true, liveBackend: false, checks: [], pageErrors: [], blockedApiRequests: [], screenshots: [] }
let browser, server, page
async function check(name, run) {
  try { await run(); report.checks.push({ name, passed: true }) }
  catch (error) { report.checks.push({ name, passed: false, error: String(error) }); if (page) await page.screenshot({ path: path.join(out, `failure-${report.checks.length}.png`), fullPage: true }).catch(() => {}) }
}
async function open(view, extra = '', width = 1440) {
  await page.setViewportSize({ width, height: 1080 })
  await page.goto(`http://127.0.0.1:5178/tests/visual/platform-workspace.html?page=${view}${extra}`, { waitUntil: 'networkidle' })
  await expect(page.locator('.platform-workspace')).toBeVisible()
  await expect(page.locator('.platform-workspace')).not.toContainText('正在加载')
  await page.evaluate(() => document.fonts.ready)
}
async function screenshot(name) {
  await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true })
  report.screenshots.push(`${name}.png`)
}
async function noOverflow() {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'page-level horizontal overflow')
}
try {
  server = await createServer({ root: path.join(root, 'frontend'), configFile: path.join(root, 'frontend/vite.config.js'), server: { host: '127.0.0.1', port: 5178, strictPort: true, open: false } })
  await server.listen()
  browser = await chromium.launch({ headless: true })
  page = await browser.newPage({ reducedMotion: 'reduce' })
  page.on('pageerror', error => report.pageErrors.push(String(error)))
  page.on('dialog', dialog => dialog.accept())
  // Match the backend root only. Vite serves source modules under /src/.../api/ too.
  await page.route(/^https?:\/\/[^/]+\/api\//, route => { report.blockedApiRequests.push(new URL(route.request().url()).pathname); return route.abort() })
  for (const view of ['overview', 'tenants', 'orders']) {
    await check(`${view}: desktop real-SFC render`, async () => { await open(view); await noOverflow(); await screenshot(`${view}-1440`) })
    await check(`${view}: narrow and tablet reflow`, async () => { for (const width of [1024, 390]) { await open(view, '', width); await noOverflow(); await screenshot(`${view}-${width}`) } })
  }
  await check('school filters, clear and compact density', async () => {
    await open('tenants')
    await page.getByRole('button', { name: '试用中', exact: true }).click()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(1)
    await page.getByRole('button', { name: '清除筛选', exact: true }).click()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(6)
    await page.getByRole('button', { name: '紧凑', exact: true }).click()
    await expect(page.locator('.pct__table-region')).toHaveClass(/compact/)
    await page.getByPlaceholder('搜索学校名称 / 编码').fill('不存在的学校')
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await expect(page.getByText('没有符合条件的学校', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '清除筛选，查看学校清单', exact: true }).click()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(6)
  })
  await check('long names and pagination preserve school identity', async () => {
    await open('tenants', '&case=long', 1024); await noOverflow()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(20)
    await page.getByRole('button', { name: '下一页', exact: true }).click()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(5)
    await screenshot('tenants-long-page2')
  })
  await check('paid repair stays separate from payment and requires typed review', async () => {
    await open('orders')
    await page.getByRole('button', { name: '激活待修复', exact: true }).click()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(1)
    await expect(page.getByRole('button', { name: '标记已支付', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '修复激活', exact: true }).click()
    await page.locator('.pcod__form textarea').fill('已核对原支付事实，仅修复激活')
    await page.getByRole('button', { name: '核对提交内容', exact: true }).click()
    await expect(page.getByRole('button', { name: '确认修复激活', exact: true })).toBeDisabled()
    await screenshot('orders-repair-review')
    await page.locator('.pcod__review input').fill('VISUAL-20260907-002')
    await page.getByRole('button', { name: '确认修复激活', exact: true }).click()
    await expect(page.locator('.pcod__receipt')).toBeVisible()
    const calls = await page.evaluate(() => window.__platformVisual.calls)
    assert.equal(calls.length, 1); assert.equal(calls[0].action, 'repair-activation'); assert.equal(calls[0].body.expectedVersion, 3)
  })
  await check('order creation shows inline form and live summary without writing', async () => {
    await open('orders')
    await page.getByRole('button', { name: '录入订单', exact: true }).click()
    await page.locator('#order-school').selectOption('1000000000000000003')
    await page.locator('#order-package').selectOption('standard')
    await expect(page.locator('.pcod__order-summary')).toContainText('星河职业技术学校')
    await screenshot('orders-create')
    assert.equal((await page.evaluate(() => window.__platformVisual.calls)).length, 0)
  })
  await check('read-only permission has no mutation buttons', async () => {
    await open('orders', '&readonly=1')
    for (const name of ['录入订单', '标记已支付', '修复激活', '取消订单']) await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
    await expect(page.locator('.dt__table')).toContainText('只读核对')
  })
  await check('missing overview evidence remains explicit', async () => {
    await open('overview', '&case=missing')
    await expect(page.locator('.pco__quality')).toContainText('文件统计来源未取得')
    await expect(page.locator('.pco__schools')).toContainText('部分学校跟进数据未取得')
    await expect(page.locator('.pco__welcome-main h2')).toContainText('先核对数据')
    await screenshot('overview-missing')
  })
  await check('failed reads do not masquerade as zero or empty success', async () => {
    for (const view of ['overview', 'tenants', 'orders']) {
      await open(view, '&case=error'); await expect(page.locator('.platform-workspace')).toContainText('读取失败')
      await expect(page.locator('.dt__table')).toHaveCount(0)
    }
    await screenshot('orders-error')
  })
  await check('overview school shortcut reaches the existing exact route', async () => {
    await open('overview')
    await page.getByRole('link', { name: '跟进明德职业技术学校', exact: true }).click()
    await expect(page.getByTestId('destination')).toBeVisible()
    assert.equal(await page.evaluate(() => window.__platformVisual.route()), '/admin/platform/tenants/1000000000000000005')
  })
  await check('no runtime exceptions or live API traffic', async () => { assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.blockedApiRequests, []) })
} finally {
  report.passed = report.checks.length > 0 && report.checks.every(check => check.passed)
  await fs.writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2))
  await browser?.close(); await server?.close()
  console.log(JSON.stringify(report, null, 2))
  if (!report.passed) process.exitCode = 1
}
