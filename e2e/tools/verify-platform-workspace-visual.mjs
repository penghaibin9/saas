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
async function detailColumns(width) {
  const geometry = await page.locator('.ptd__cols').evaluate(grid => {
    const rect = node => { const r = node.getBoundingClientRect(); return { x: r.x, right: r.right, y: r.y, width: r.width } }
    return { grid: rect(grid), cards: [...grid.querySelectorAll(':scope > .ptd__panel')].map(rect), lifecycle: rect(grid.querySelector('.tlw')) }
  })
  assert.equal(geometry.cards.length, 2)
  assert.ok(Math.abs(geometry.lifecycle.width - geometry.grid.width) < 2, 'lifecycle should span the whole workspace')
  if (width > 760) {
    assert.ok(geometry.cards.every(card => card.width > geometry.grid.width * .45), 'overview cards must use both halves, not leave empty tracks')
    assert.ok(Math.abs(geometry.cards[0].y - geometry.cards[1].y) < 2, 'desktop overview cards should share one row')
    assert.ok(Math.abs(geometry.cards[1].right - geometry.grid.right) < 2, 'no unused right-side grid tracks')
  } else {
    assert.ok(geometry.cards.every(card => Math.abs(card.width - geometry.grid.width) < 2), 'narrow cards must use the full available width')
    assert.ok(geometry.cards[1].y > geometry.cards[0].y, 'narrow cards should stack vertically')
  }
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
  for (const view of ['overview', 'tenants', 'orders', 'detail']) {
    await check(`${view}: desktop real-SFC render`, async () => { await open(view); await noOverflow(); if (view === 'detail') await detailColumns(1440); await screenshot(`${view}-1440`) })
    await check(`${view}: narrow and tablet reflow`, async () => { for (const width of [1024, 390]) { await open(view, '', width); await noOverflow(); if (view === 'detail') await detailColumns(width); await screenshot(`${view}-${width}`) } })
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
    await expect(page.locator('.pct__empty').getByRole('button', { name: '返回', exact: true })).toHaveCount(0)
    await screenshot('tenants-empty-recovery')
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
    for (const view of ['overview', 'tenants', 'orders', 'detail']) {
      await open(view, '&case=error'); await expect(page.locator('.platform-workspace')).toContainText('读取失败')
      await expect(page.locator('.dt__table')).toHaveCount(0)
    }
    await screenshot('orders-error')
  })
  await check('overview school shortcut reaches the existing exact route', async () => {
    await open('overview')
    await page.getByRole('link', { name: '跟进明德职业技术学校', exact: true }).click()
    await expect(page.getByRole('heading', { name: '明德职业技术学校', exact: true })).toBeVisible()
    assert.equal(await page.evaluate(() => window.__platformVisual.route()), '/admin/platform/tenants/1000000000000000005')
  })
  await check('orders have a recoverable empty search including the local work-item filter', async () => {
    await open('orders')
    await page.getByRole('button', { name: '激活待修复', exact: true }).click()
    await page.getByPlaceholder('搜索学校名称 / 订单号').fill('不存在的订单')
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await expect(page.getByText('当前条件下没有订单', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '返回', exact: true })).toHaveCount(0)
    await screenshot('orders-empty-recovery')
    await page.getByRole('button', { name: '清除筛选，查看订单清单', exact: true }).click()
    await expect(page.locator('.dt__table tbody tr')).toHaveCount(6)
    assert.equal((await page.evaluate(() => window.__platformVisual.calls)).length, 0)
  })
  await check('empty read-only orders do not invent create or back actions', async () => {
    await open('orders', '&case=empty&readonly=1')
    await expect(page.getByText('当前条件下没有订单', { exact: true })).toBeVisible()
    for (const name of ['返回', '录入首笔订单', '录入订单']) await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  })
  await check('narrow school table has a useful scroll hint and a styled usage meter', async () => {
    await open('tenants', '', 390)
    await expect(page.locator('#pct-table-help')).toBeVisible()
    await expect(page.locator('.pct__table-region')).toHaveAttribute('aria-describedby', 'pct-table-help')
    assert.equal(await page.locator('progress').first().evaluate(node => getComputedStyle(node).appearance), 'none')
    await page.locator('.pct__table-region').focus()
    await noOverflow()
  })
  await check('school lifecycle cannot lose its preview or draft through a tab switch', async () => {
    await open('detail')
    await page.getByRole('button', { name: '停用学校', exact: true }).click()
    await page.locator('.tlw textarea').fill('学校维护期间临时停用服务')
    await page.getByRole('button', { name: '品牌（只读）', exact: true }).click()
    await expect(page.locator('.ptd__leave-rules')).toContainText('学校变更尚未办理完毕')
    await page.getByRole('button', { name: '继续办理', exact: true }).click()
    await expect(page.locator('.tlw textarea')).toHaveValue('学校维护期间临时停用服务')
    await page.getByRole('button', { name: '查看变更影响', exact: true }).click()
    await expect(page.getByRole('button', { name: '确认停用学校', exact: true })).toBeDisabled()
    await screenshot('detail-lifecycle-review')
    await page.locator('.tlw__preview input').fill('VISUAL-1')
    await page.getByRole('button', { name: '确认停用学校', exact: true }).click()
    await expect(page.locator('.tlw__receipt')).toContainText('变更已生效')
    assert.equal((await page.evaluate(() => window.__platformVisual.calls)).length, 1)
  })
  await check('rule workspace renders real typed fields, draft protection and sparse save', async () => {
    await open('detail', '&tab=rules')
    await page.locator('.trw__search input').fill('uploadMaxSizeMb')
    await page.locator('.trw input[type=number]').fill('30')
    await page.locator('#rules-change-reason').fill('学校文件容量上限调整说明')
    await page.getByRole('button', { name: '品牌（只读）', exact: true }).click()
    await expect(page.locator('.ptd__leave-rules')).toBeVisible()
    await page.getByRole('button', { name: '继续办理', exact: true }).click()
    await page.getByRole('button', { name: '核对 1 项修改', exact: true }).click()
    await screenshot('detail-rules-review')
    await page.getByRole('button', { name: '确认保存规则', exact: true }).click()
    await expect(page.locator('.trw__success')).toContainText('规则保存成功')
    const calls = await page.evaluate(() => window.__platformVisual.calls)
    assert.equal(calls.length, 1); assert.deepEqual(calls[0].patch, { file: { uploadMaxSizeMb: 30 } }); assert.equal(calls[0].expectedVersion, 4)
  })
  await check('read-only rules and canonical brand remain non-writable', async () => {
    await open('detail', '&tab=rules&readonly=1', 390)
    await expect(page.locator('.trw')).toContainText('当前身份只读')
    await expect(page.locator('#student\\.studentNoRequired')).toBeDisabled()
    await noOverflow(); await screenshot('detail-rules-readonly-390')
    await page.getByRole('button', { name: '品牌（只读）', exact: true }).click()
    await expect(page.locator('.ptd__brand')).toContainText('学校数字服务')
    await expect(page.locator('.ptd__brand input')).toHaveCount(0)
    await noOverflow(); await screenshot('detail-brand-390')
  })
  await check('empty school tabs show exact contextual titles with working recovery', async () => {
    for (const [tab, title] of [['features', '接口未返回可展示的授权项'], ['workflows', '当前学校暂无运行流程定义'], ['users', '该学校暂无账号']]) {
      await open('detail', `&tab=${tab}&case=empty`)
      await expect(page.getByText(title, { exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: '返回', exact: true })).toHaveCount(0)
      await page.getByRole('button', { name: '返回学校概况', exact: true }).click()
      await expect(page.locator('.tlw')).toBeVisible()
    }
  })
  await check('no runtime exceptions or live API traffic', async () => { assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.blockedApiRequests, []) })
} finally {
  report.passed = report.checks.length > 0 && report.checks.every(check => check.passed)
  await fs.writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2))
  await browser?.close(); await server?.close()
  console.log(JSON.stringify(report, null, 2))
  if (!report.passed) process.exitCode = 1
}
