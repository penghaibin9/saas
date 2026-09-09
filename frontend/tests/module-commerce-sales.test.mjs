import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { moneyCents, lineAmount, localInputToUtc, utcToLocalInput, renewalInputFromUtc, newOrderAttempt, restoreOrderAttempt, isDefinitiveRejection } from '../src/modules/platform/lib/moduleCommerceSales.mjs'

test('decimal prices and discounts remain exact at the contract limit', () => {
  assert.equal(moneyCents('9999999999.99'), 999999999999n)
  assert.equal(lineAmount('0.10', 3, '0.01'), '0.29')
  assert.equal(lineAmount('100.00', 1, '100.00'), '0.00')
})
test('invalid prices, float inputs, quantities and overflow never silently round', () => {
  for (const value of [0.1, true, null, '', '0.001', '1e2', 'NaN', '-1', '01', '10000000000.00']) {
    assert.throws(() => moneyCents(value), String(value))
  }
  for (const qty of [0, 1.5, '3', true, 1000001]) assert.throws(() => lineAmount('1.00', qty, '0'))
  assert.throws(() => lineAmount('1.00', 1, '1.01'))
  assert.throws(() => lineAmount('9999999999.99', 2, '0'))
})
test('sales input always means Asia/Shanghai regardless of browser timezone', () => {
  assert.equal(localInputToUtc('2026-09-09T08:00'), '2026-09-09T00:00:00Z')
  assert.equal(localInputToUtc('2026-01-01T00:00:01'), '2025-12-31T16:00:01Z')
  assert.equal(utcToLocalInput('2026-09-09T00:00:00Z'), '2026-09-09T08:00:00')
  assert.equal(localInputToUtc('2028-02-29T08:00'), '2028-02-29T00:00:00Z')
})
test('invalid calendar inputs are not normalized into another service day', () => {
  for (const date of ['', '2026-02-30T12:00', '2026-02-29T12:00', '2026-13-01T12:00', '2026-01-01T25:00', '2026-01-01', '2026-01-01T12:00Z']) assert.throws(() => localInputToUtc(date), date)
})
test('pending commands retain exact key and detached payload across tab reload', () => {
  const source = {tenantId:'1000000000000000001', items:[{unitPrice:'0.10'}]}
  const attempt = newOrderAttempt(source, () => 'unique-uuid')
  source.items[0].unitPrice='999'
  assert.equal(attempt.order.items[0].unitPrice, '0.10')
  const restored = restoreOrderAttempt(JSON.stringify(attempt), source.tenantId)
  assert.deepEqual(restored, attempt)
  assert.equal(restored.key, 'module-sale-unique-uuid')
})
test('corrupt or another school pending payload cannot be reused', () => {
  assert.equal(restoreOrderAttempt(null, '42'), null)
  for (const raw of ['bad json', '{}', JSON.stringify({key:'correct-long-key',order:{tenantId:'43',items:[]}})]) assert.throws(() => restoreOrderAttempt(raw,'42'))
})
test('409, 403, 503 and timeout do not prove the original order never committed', () => {
  for (const bizCode of ['DATA_CONFLICT','NO_PERMISSION','DATA_NOT_FOUND','SERVER_ERROR','REQUEST_TIMEOUT','SESSION_CHANGED']) assert.equal(isDefinitiveRejection({bizCode}),false)
  assert.equal(isDefinitiveRejection({details:{salesCommandNotCommitted:'true'}}),false)
  assert.equal(isDefinitiveRejection({details:{salesCommandNotCommitted:true}}),true)
})
test('workspace uses actual APIs, authenticated duties and no implicit paid action', () => {
  const source=fs.readFileSync(fileURLToPath(new URL('../src/modules/platform/views/control/ModuleSalesWorkspace.vue',import.meta.url)),'utf8')
  for (const seam of ['api.listSaleSkus','api.previewSalesOrder','api.createSalesOrder','api.listSalesOrders','api.getSalesOrder','api.exportSalesOrders','api.publishSku','api.getSalesContext','api.listSalesTenants']) assert.ok(source.includes(seam),seam)
  assert.ok(source.includes('ensurePlatformAccessContext({force:true})'))
  assert.ok(source.includes('id===props.tenantId'))
  assert.ok(source.indexOf('sessionStorage.setItem(storageKey()') < source.indexOf('await api.createSalesOrder'))
  assert.ok(source.includes('api.createSalesOrder(command.order,command.key)'))
  assert.ok(!source.includes("'mark-paid'"))
  const parent=fs.readFileSync(fileURLToPath(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue',import.meta.url)),'utf8')
  assert.ok(parent.includes('<ModuleSalesWorkspace'))
  assert.ok(parent.includes('id!==this.selectedTenantId||seq!==this.portfolioSeq'))
})

test('legacy fractional paid boundaries round upward rather than overlap', () => {
  assert.equal(renewalInputFromUtc('2026-09-09T00:00:00.000001Z'), '2026-09-09T08:00:01')
  assert.equal(renewalInputFromUtc('2026-09-09T00:00:00.999999Z'), '2026-09-09T08:00:01')
  assert.equal(renewalInputFromUtc('2026-09-09T00:00:00.000000Z'), '2026-09-09T08:00:00')
})
