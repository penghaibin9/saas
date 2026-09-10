import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const stateSource = await readFile(new URL('../src/pages/student/academic-affairs/selection-state.js', import.meta.url), 'utf8')
const state = await import(`data:text/javascript;base64,${Buffer.from(stateSource).toString('base64')}`)

test('selection statuses keep lottery, confirmed seats and terminal outcomes distinct', () => {
  assert.equal(state.selectionStatusMeta('PENDING_LOTTERY').label, '已报名待抽签')
  assert.equal(state.selectionStatusMeta('SELECTED').label, '已取得名额')
  assert.equal(state.selectionStatusMeta('LOCKED').label, '名单已锁定')
  assert.equal(state.selectionStatusMeta('LOTTERY_LOST').label, '未中签')
  assert.equal(state.selectionStatusMeta('DROPPED').label, '已退课')
  assert.equal(state.selectionStatusMeta('COURSE_CANCELLED').label, '课程取消')
  assert.equal(state.hasConfirmedSeat({ status: 'PENDING_LOTTERY' }), false)
  assert.equal(state.hasConfirmedSeat({ status: 'SELECTED' }), true)
})

test('unknown records stay visible and transport uncertainty requires reconciliation', () => {
  assert.equal(state.isVisibleSelectionRecord({ recordId: 'r1', status: 'NEW_SERVER_STATE' }), true)
  assert.equal(state.selectionStatusMeta('NEW_SERVER_STATE').label, '状态待核实')
  assert.equal(state.isUncertainSelectionError({ code: 429, biz: true }), true)
  assert.equal(state.isUncertainSelectionError({ code: 'SERVER_ERROR', httpStatus: 503, biz: true }), true)
  assert.equal(state.isUncertainSelectionError({ errMsg: 'request:fail timeout' }), true)
  assert.equal(state.isUncertainSelectionError({ code: 403, biz: true }), false)
  assert.equal(state.isUncertainSelectionError({ code: 409, biz: true }), false)
  assert.equal(state.isUncertainSelectionError({ biz: true, code: 'COURSE_FULL' }), false)
})

test('a readback must establish the requested operation, not merely contain any old record', () => {
  assert.equal(state.recordConfirmsOperation({ status: 'SELECTED' }, 'DROP'), false)
  assert.equal(state.recordConfirmsOperation({ status: 'DROPPED' }, 'DROP'), true)
  assert.equal(state.recordConfirmsOperation({ status: 'DROPPED' }, 'ENROLL'), false)
  assert.equal(state.recordConfirmsOperation(null, 'ENROLL'), false)
  assert.equal(state.recordConfirmsOperation({ status: 'NEW_SERVER_STATE' }, 'ENROLL'), false)
  assert.equal(state.recordConfirmsOperation({ status: 'PENDING_LOTTERY' }, 'ENROLL'), true)
})
