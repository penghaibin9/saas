import fs from 'node:fs/promises'
import path from 'node:path'
import { expect } from './observability.mjs'
import { config } from './config.mjs'

/** Reuse the W12 real root browser session; never manufacture auth or mock an API. */
export async function verifyPlatformOrderWorkspace(page, token, browserApiRaw) {
  const tenantCode = `order-ui-${process.env.GITHUB_RUN_ID || Date.now()}`
  const request = async (requestPath, method = 'GET', body) => {
    const result = await browserApiRaw(page, token, requestPath, { method, body })
    expect(result.status, JSON.stringify(result.json)).toBe(200)
    expect(result.json?.code, JSON.stringify(result.json)).toBe(0)
    return result.json.data
  }
  const school = await request('/platform/tenants', 'POST', {
    tenantCode, tenantName: '合同订单工作区验收学校', packageCode: 'trial'
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(new URL(`/admin/platform/orders?tenantId=${school.tenantId}`, config.staffBaseUrl).toString())
  await expect(page.getByRole('heading', { name: '合同订单与授权', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '录入合同订单', exact: true })).toHaveCount(0)
  await expect(page.getByText('当前条件下没有订单', { exact: true })).toBeVisible()

  async function createInWorkspace(amount) {
    await page.getByRole('button', { name: '录入订单', exact: true }).click()
    await page.locator('#order-school').selectOption(school.tenantId)
    await page.locator('#order-package').selectOption('standard')
    await page.locator('#order-amount').fill(amount)
    await page.locator('#order-days').fill('30')
    await page.getByRole('button', { name: '核对提交内容', exact: true }).click()
    await expect(page.locator('.pcod__review')).toContainText('合同订单工作区验收学校')
    await page.locator('.pcod__review input').fill(tenantCode)
    const response = page.waitForResponse(res => new URL(res.url()).pathname === '/api/v1/platform/orders' && res.request().method() === 'POST')
    await page.getByRole('button', { name: '确认创建未支付订单', exact: true }).click()
    const payload = await (await response).json()
    expect(payload.code, JSON.stringify(payload)).toBe(0)
    await expect(page.getByRole('heading', { name: '未支付订单已创建', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '返回并刷新订单清单', exact: true }).click()
    const order = payload.data
    await expect(page.getByRole('row').filter({ hasText: order.orderNo })).toContainText('待支付')
    return order
  }

  async function actInWorkspace(order, action, label, expectedHeading) {
    const row = page.getByRole('row').filter({ hasText: order.orderNo })
    await row.getByRole('button', { name: label, exact: true }).click()
    await page.locator('.pcod__form textarea').fill('真实浏览器核验合同与办理原因')
    await page.getByRole('button', { name: '核对提交内容', exact: true }).click()
    await page.locator('.pcod__review input').fill(order.orderNo)
    const response = page.waitForResponse(res => new URL(res.url()).pathname === `/api/v1/platform/orders/${order.orderNo}/${action}` && res.request().method() === 'POST')
    await page.getByRole('button', { name: `确认${label}`, exact: true }).click()
    const payload = await (await response).json()
    expect(payload.code, JSON.stringify(payload)).toBe(0)
    await expect(page.getByRole('heading', { name: expectedHeading, exact: true })).toBeVisible()
    await page.getByRole('button', { name: '返回并刷新订单清单', exact: true }).click()
    return payload.data
  }

  const bought = await createInWorkspace('1200.50')
  const paid = await actInWorkspace(bought, 'mark-paid', '标记已支付', '支付已入账，授权已激活')
  expect(paid.tenantActivated).toBe(true)
  expect(paid.repairTaskRequired).toBe(false)
  const features = await request(`/platform/tenants/${school.tenantId}/features`)
  expect(features.authoritySource).toBe('PAID_ORDER')
  expect(features.commercialOrderNo).toBe(bought.orderNo)
  expect(features.packageCode).toBe('standard')
  const paidRow = page.getByRole('row').filter({ hasText: bought.orderNo })
  await expect(paidRow).toContainText('已支付')
  await expect(paidRow).toContainText('已激活')
  await expect(paidRow.getByRole('button', { name: '标记已支付', exact: true })).toHaveCount(0)

  const cancelledOrder = await createInWorkspace('500.00')
  const cancelled = await actInWorkspace(cancelledOrder, 'cancel', '取消订单', '订单已取消')
  expect(cancelled.status).toBe('cancelled')
  const stale = await browserApiRaw(page, token, `/platform/orders/${cancelledOrder.orderNo}/cancel`, {
    method: 'POST', body: { expectedVersion: cancelledOrder.version, reason: '核验旧版本不能重放取消' }
  })
  expect(stale.status).toBe(409)
  expect(stale.json?.bizCode).toBe('DATA_CONFLICT')
  const listed = await request(`/platform/orders?tenantId=${school.tenantId}`)
  expect(listed.list).toHaveLength(2)
  expect(listed.list.find(item => item.orderNo === bought.orderNo).status).toBe('paid')
  expect(listed.list.find(item => item.orderNo === cancelledOrder.orderNo).status).toBe('cancelled')
  await expect(page.getByRole('row').filter({ hasText: cancelledOrder.orderNo })).toContainText('已取消')
  await fs.mkdir(path.resolve('test-results'), { recursive: true })
  await page.screenshot({ path: path.resolve('test-results/platform-order-workspace-1440.png'), fullPage: true })
  await page.setViewportSize({ width: 1366, height: 900 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  await page.screenshot({ path: path.resolve('test-results/platform-order-workspace-1366.png'), fullPage: true })
  await fs.writeFile(path.resolve('test-results/platform-order-workspace-evidence.json'), JSON.stringify({
    headSha: process.env.E2E_EXPECTED_SHA, realBrowser: true, realApi: true, mockSuccess: false,
    queryDoesNotCreate: true, createdUnpaid: true, paidOrderAuthorityVerified: true,
    cancelledWithoutRevokingPaidOrder: true, staleVersionRejected: true, tenantId: school.tenantId,
    orderNos: [bought.orderNo, cancelledOrder.orderNo]
  }, null, 2))
}
