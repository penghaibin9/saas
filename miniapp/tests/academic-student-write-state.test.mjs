import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../src/pages/student/academic-affairs/write-state.js', import.meta.url), 'utf8')
const state = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)

test('academic writes distinguish transport uncertainty from server business rejection', () => {
  assert.equal(state.isUncertainWriteError({ errMsg: 'request:fail timeout' }), true)
  assert.equal(state.isUncertainWriteError({ code: 429, biz: true }), true)
  assert.equal(state.isUncertainWriteError({ code: 'SERVER_ERROR', httpStatus: 500, biz: true }), true)
  assert.equal(state.isUncertainWriteError({ code: 403, biz: true }), false)
  assert.equal(state.isUncertainWriteError({ code: 409, biz: true }), false)
})
