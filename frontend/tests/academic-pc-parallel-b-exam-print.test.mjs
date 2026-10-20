import test from 'node:test'
import assert from 'node:assert/strict'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { isDefiniteWriteRejection } from '../src/modules/academicAffairs/components/parallel-b/unconfirmedWrite.js'

function printPage(api) {
  const markers = new Map()
  const result = page('AaExamSeatingPrintView', {
    academicAffairsExamPrintApi: api,
    isDefiniteWriteRejection,
    readUnconfirmedWrite: key => markers.get(key) || null,
    markUnconfirmedWrite: (key, value) => markers.set(key, value),
    clearUnconfirmedWrite: key => markers.delete(key)
  })
  result.state.roomId = 'a'
  return result
}

const document = id => ({
  documentStatus: 'OFFICIAL',
  examRoomId: id,
  printIdentity: 'proof-' + id,
  seats: [{ studentNo: 'test-1', seatNo: 1 }]
})

test('old formal print response cannot replace the newly selected room', async () => {
  const old = deferred()
  const { state } = printPage({ formalRoomPrint: () => old.promise })
  const pending = state.load()
  state.roomId = 'b'
  old.resolve(document('a'))
  await pending
  assert.equal(state.document, null)
  assert.equal(state.canPrint, false)
})

test('formal provider must return the exact requested room', async () => {
  const { state } = printPage({ formalRoomPrint: async () => document('b') })
  await state.load()
  assert.equal(state.canPrint, false)
  assert.match(state.error, /不一致/)
})

test('print confirmation cannot send an audit for a different room', async () => {
  let writes = 0
  const { state } = printPage({ issueFormalPrint: async () => { writes++; return {} } })
  state.document = document('a')
  state.rows = state.document.seats
  state.openPrint('DOOR_LIST')
  state.roomId = 'b'
  await state.issueAndPrint()
  assert.equal(writes, 0)
})

test('unknown audit write blocks repeat audit and never schedules printing', async () => {
  let writes = 0
  let prints = 0
  const { state } = printPage({
    issueFormalPrint: async () => {
      writes++
      throw Object.assign(new Error('timeout'), { code: 503002 })
    }
  })
  state.document = document('a')
  state.rows = state.document.seats
  state.$nextTick = () => { prints++ }
  state.openPrint('DOOR_LIST')
  await state.issueAndPrint()
  await state.issueAndPrint()
  assert.equal(writes, 1)
  assert.equal(prints, 0)
})
