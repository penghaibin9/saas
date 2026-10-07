import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/FundingWorkbenchView.vue', import.meta.url), 'utf8').replaceAll('\r','')
const body = source.match(/ {4}detailActions\(\) \{([\s\S]*?)\n {4}\}\n {2}\},/)[1]
const actions = selected => new Function('FUND_NODES', body).call({selected}, ['COUNSELOR_REVIEW','COLLEGE_REVIEW','SCHOOL_REVIEW'])

test('PC funding review never invents review actions from node or administrator role', () => {
  assert.deepEqual(actions({status:'COUNSELOR_REVIEW'}), [])
  assert.deepEqual(actions({status:'COUNSELOR_REVIEW', allowedActions:[]}), [])
  assert.deepEqual(actions({status:'COUNSELOR_REVIEW', allowedActions:['APPROVE','RETURN','REJECT']}).map(x=>x.key), ['approve','return','reject'])
  assert.deepEqual(actions({status:'RETURNED', allowedActions:[]}), [])
})
