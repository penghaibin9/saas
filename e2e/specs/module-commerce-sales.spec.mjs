import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

test('commercial operator publishes, previews, creates unpaid order and reads frozen lines after refresh', async ({ page, context }, testInfo) => {
  const fixture = JSON.parse(fs.readFileSync(path.resolve('runtime-fixtures/module-commerce-sales.json'), 'utf8'))
  const session = fixture.session
  const digest = crypto.createHash('sha256').update(session.browserSessionId).digest('hex').slice(0, 24)
  await context.addCookies([{
    name: `gx_platform_refresh_v2_${digest}`, value: session.refreshToken,
    domain: new URL(config.staffBaseUrl).hostname, path: '/api/v1/auth',
    httpOnly: true, secure: false, sameSite: 'Strict'
  }])
  await context.addInitScript(id => sessionStorage.setItem('gx_browser_session_id_v2', id), session.browserSessionId)
  await page.goto(new URL('/admin/platform/commercial-control', config.staffBaseUrl).toString())
  const sales = page.getByRole('region', { name: '模块商品销售工作区' })
  await expect(sales).toBeVisible()
  await sales.getByLabel('检索学校', { exact: true }).fill(fixture.schools[0].tenantCode)
  await sales.getByRole('button', { name: '查询', exact: true }).click()
  await expect(sales.getByLabel('办理学校')).toBeEnabled()
  await sales.getByLabel('办理学校').selectOption(fixture.schools[0].tenantId)
  const code = `E2E-M3-${crypto.randomUUID().slice(0, 8)}`
  await sales.getByRole('tab', { name: '商品版本', exact: true }).click()
  const catalog = sales.getByRole('tabpanel', { name: '商品版本', exact: true })
  await catalog.getByRole('combobox', { name: '模块', exact: true }).selectOption('internship')
  await catalog.getByLabel('商品名称', { exact: true }).fill('隔离测试实习商品')
  await catalog.getByLabel('SKU编码', { exact: true }).fill(code)
  await catalog.getByLabel('目录单价（CNY）', { exact: true }).fill('0.10')
  await catalog.getByLabel('生命周期政策版本', { exact: true }).fill('E2E-NO-PRODUCTION-POLICY')
  await catalog.getByLabel('发布原因', { exact: true }).fill('隔离浏览器验证商品，不用于真实销售')
  const published = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/platform/commercial/skus'))
  await catalog.getByRole('button', { name: '发布商品版本（不授权学校）', exact: true }).click()
  expect((await published).status()).toBe(200)
  await expect(sales.getByText(/没有给学校新增授权/)).toBeVisible()
  await sales.getByRole('tab', { name: '分项订购与续费', exact: true }).click()
  await sales.getByLabel('检索商品', { exact: true }).fill(code)
  await sales.getByRole('button', { name: '查询商品', exact: true }).click()
  await sales.getByRole('button').filter({ hasText: code }).click()
  await sales.getByLabel('合同 / 报价说明', { exact: true }).fill('隔离浏览器合同，仅验证未支付销售链')
  await sales.getByLabel('数量', { exact: true }).fill('3')
  await sales.getByLabel('优惠金额', { exact: true }).fill('0.01')
  await sales.getByLabel('服务开始（北京时间）', { exact: true }).fill('2026-09-10T00:00')
  await sales.getByLabel('服务截止（北京时间，不含）', { exact: true }).fill('2027-09-10T00:00')
  await sales.getByRole('button', { name: '核算金额与服务期', exact: true }).click()
  await expect(sales.locator('.quote-total')).toHaveText('CNY 0.29')
  await sales.getByRole('checkbox', { name: /我已核对学校/ }).check()
  const created = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/platform/commercial/sales-orders'))
  await sales.getByRole('button', { name: '创建未支付订单', exact: true }).click()
  const result = await (await created).json()
  expect(result.code).toBe(0)
  expect(result.data.paymentRecorded).toBe(false)
  expect(result.data.rightsMaterialized).toBe(false)
  const orderNo = result.data.orderNo
  await sales.getByRole('button', { name: '查看该校分项台账', exact: true }).click()
  const row = sales.getByRole('row').filter({ hasText: orderNo })
  await expect(row).toContainText('未支付')
  await expect(row).toContainText('CNY 0.29')
  await row.getByRole('button', { name: '查看冻结分项' }).click()
  await expect(sales.locator('.detail')).toContainText(code)
  await expect(sales.locator('.detail')).toContainText('0.29')
  await sales.screenshot({ path: testInfo.outputPath('sales-frozen-ledger.png') })
  await sales.getByLabel('导出原因', { exact: true }).fill('隔离浏览器核对合同台账')
  const download = page.waitForEvent('download')
  await sales.getByRole('button', { name: '导出此条件的 xlsx', exact: true }).click()
  const file = await download
  expect(file.suggestedFilename()).toMatch(/\.xlsx$/)
  await file.saveAs(testInfo.outputPath('sales-ledger.xlsx'))
  await page.reload()
  await expect(sales).toBeVisible()
  await sales.getByLabel('检索学校', { exact: true }).fill(fixture.schools[0].tenantCode)
  await sales.getByRole('button', { name: '查询', exact: true }).click()
  await expect(sales.getByLabel('办理学校')).toBeEnabled()
  await sales.getByLabel('办理学校').selectOption(fixture.schools[0].tenantId)
  await sales.getByRole('tab', { name: '分项订单台账', exact: true }).click()
  await expect(sales.getByRole('row').filter({ hasText: orderNo })).toContainText('未支付')
})
