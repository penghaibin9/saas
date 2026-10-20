import test from 'node:test'
import assert from 'node:assert/strict'
import * as contracts from '../src/modules/platform/utils/orderWorkspace.mjs'
import { optionsInstance, plain } from './platform-workspace-test-support.mjs'
const orderPath = '../src/modules/platform/views/control/PlatformControlOrders.vue'
const schoolPath = '../src/modules/platform/views/control/PlatformControlTenants.vue'
const make = (state = {}) => optionsInstance(orderPath, state, contracts).state
const rows = [
  { tenantId: '1000000000000000003', orderNo: 'PO-1', tenantName: '甲学校', status: 'unpaid', version: 1 },
  { tenantId: '1000000000000000003', orderNo: 'PO-2', tenantName: '甲学校', status: 'paid', activationState: 'REPAIR_REQUIRED', repairTaskRequired: true, version: 2 },
  { tenantId: '1000000000000000003', orderNo: 'PO-3', tenantName: '甲学校', status: 'paid', activationState: 'ACTIVE', repairTaskRequired: false, version: 3 },
  { tenantId: '1000000000000000004', orderNo: 'PO-4', tenantName: '乙学校', status: 'paid', activationState: 'ACTIVE', version: 3 }
]
test('order task filters distinguish payment work from activation repair', () => {
  const state = make({ rows, loading: false })
  state.page = 3; state.selectFocus('repair')
  assert.equal(state.page, 1)
  assert.deepEqual(plain(state.filteredRows.map(row => row.orderNo)), ['PO-2'])
  assert.deepEqual(plain(state.orderActions(state.filteredRows[0])), ['repair-activation'])
  state.selectFocus('unpaid')
  assert.deepEqual(plain(state.filteredRows.map(row => row.orderNo)), ['PO-1'])
  state.selectFocus('unknown'); assert.equal(state.focus, 'unpaid')
})
test('order summary follows the search scope without shrinking to the selected task tab', () => {
  const state = make({ rows, loading: false, scope: { keyword: '甲学校', status: '', tenantId: '' } })
  state.selectFocus('repair')
  assert.deepEqual(plain(state.summaryMetrics.map(item => item.value)), [3, 1, 1, 1])
  assert.equal(state.filteredRows.length, 1)
})
test('unknown and failed order reads never produce zero summary totals', () => {
  const state = make({ rows, loading: true })
  assert.ok(state.summaryMetrics.every(item => item.value === '未取得'))
  state.loading = false; state.error = '读取失败'
  assert.ok(state.summaryMetrics.every(item => item.value === '未取得'))
})
test('a paid order with unknown activation evidence does not acquire a green activation badge', () => {
  const state = make()
  assert.equal(state.paymentStatus(rows[3]).label, '已支付')
  assert.equal(state.activationStatus(rows[3]).label, '激活待核验')
  assert.notEqual(state.activationStatus(rows[3]).tone, 'success')
  assert.equal(state.activationStatus(rows[2]).label, '已激活')
  assert.equal(state.activationStatus(rows[1]).label, '激活待修复')
})
test('order progress and summary reflect the active business object', () => {
  const state = make({ phase: 'edit', work: { kind: 'create' }, form: { tenantId: rows[0].tenantId }, tenants: [rows[0]] })
  assert.equal(state.summarySchool, '甲学校'); assert.equal(state.workStep, 0)
  state.phase = 'review'; assert.equal(state.workStep, 1)
  state.phase = 'uncertain'; assert.equal(state.workStep, 2)
  state.form.tenantId = '999'; assert.equal(state.summarySchool, '选择学校后显示订单摘要')
})
test('school summary counts only known states and never treats unknown as active', () => {
  const { state } = optionsInstance(schoolPath, { loading: false, rows: ['active', 'trial', 'expired', 'disabled', 'UNKNOWN'].map(status => ({ status })) })
  assert.deepEqual(plain(state.schoolMetrics.map(item => item.value)), [5, 1, 1, 2])
  state.error = '读取失败'; assert.ok(state.schoolMetrics.every(item => item.value === '未取得'))
})
test('changing school density neither mutates objects nor invokes an API', () => {
  const { state, calls } = optionsInstance(schoolPath, { rows: [{ tenantId: '1', status: 'active' }] })
  const before = JSON.stringify(state.rows)
  state.density = 'compact'; assert.equal(JSON.stringify(state.rows), before)
  assert.equal(calls.length, 0)
  assert.equal(state.rowTone({ status: 'expired' }), 'pct__service-attention')
  assert.equal(state.rowTone({ status: 'active' }), '')
})
