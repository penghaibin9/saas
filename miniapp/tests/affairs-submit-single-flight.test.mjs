import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

for (const [page, method, apiName] of [
  ['loan', 'submit', 'submitLoan'], ['loan', 'withdraw', 'withdrawLoan'],
  ['reduction', 'submit', 'submitFeeReduction'], ['reduction', 'withdraw', 'withdrawFeeReduction'],
  ['work-study', 'submitApply', 'applyWorkStudy'], ['work-study', 'withdraw', 'withdrawWorkStudy'],
  ['discipline', 'appeal', 'appeal']
]) test(`${page}: double ${method} executes one business command`, async () => {
  const source = readFileSync(new URL(`../src/pages/student/affairs/${page}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
  let finish, calls = 0
  const pending = new Promise(resolve => { finish = resolve })
  const write = () => { calls++; return pending }
  const component = new Function('studentApi', 'affairsDisciplineAppeal', 'normalizeError', 'toast', 'uni', script)({ [apiName]: write }, write, e => ({ text: e.message }), () => {}, { showToast() {} })
  const vm = { ...component.data(), ...component.methods, formValid: true,
    load: async () => {}, loadPosts: async () => {}, loadRecords: async () => {}, payload: () => ({}),
    applyTarget: { postId: '1' }, reasons: { '1': '申请复核具体处分事实' } }
  const row = { loanId: '1', feeId: '1', recordId: '1', caseId: '1', version: 3 }
  const first = vm[method](row)
  const second = vm[method](row)
  const count = calls
  finish({})
  await Promise.all([first, second])
  assert.equal(count, 1)
})
