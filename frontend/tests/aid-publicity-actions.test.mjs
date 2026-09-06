import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Execute the real component method so dropping the observed version breaks this regression.
const source = readFileSync(new URL('../src/modules/studentAffairs/views/aid/AidPublicityView.vue', import.meta.url), 'utf8')
const method = source.match(/async confirm\(it\) \{([\s\S]*?)\n {4}\},\n {4}levelLabel/)[1]
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const invoke = new AsyncFunction('studentAffairsApi', 'toast', 'it', method)

test('publicity confirmation sends the displayed version and blocks repeated clicks', async () => {
  let finish
  const calls = []
  const api = { confirmAidPublicity: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve }) } }
  const ctx = { actingId: '', scanning: false, pagination: {page: 2}, load: async () => { ctx.refreshed = true } }
  const toast = { success() {}, error() {} }
  const row = {applyId:'9007199254740993', version:7, publicityReady:true}
  const pending = invoke.call(ctx, api, toast, row)
  await invoke.call(ctx, api, toast, row)
  assert.deepEqual(calls, [[row.applyId, 7]])
  finish({code:0})
  await pending
  assert.equal(ctx.refreshed, true)
  assert.equal(ctx.actingId, '')
})

test('stale and uncertain results never retry with a new version and always release busy state', async () => {
  for (const failure of [{code:409, message:'版本冲突，请刷新'}, new Error('network')]) {
    let calls = 0
    const messages = []
    const ctx = {actingId:'', scanning:false, pagination:{page:2}, load:async () => assert.fail('must not treat failure as success')}
    const api = {confirmAidPublicity:async () => { calls++; if (failure instanceof Error) throw failure; return failure }}
    await invoke.call(ctx, api, {success:()=>assert.fail('false success'), error:m=>messages.push(m)}, {applyId:'1',version:3,publicityReady:true})
    assert.equal(calls, 1)
    assert.equal(ctx.actingId, '')
    assert.equal(ctx.pagination.page, 2)
    assert.match(messages[0], /刷新/)
  }
})

test('not-yet-due and contested applications cannot submit a confirmation from the list', async () => {
  for (const row of [{publicityReady:false}, {publicityReady:true,hasPendingObjection:true}, {}]) {
    let message = ''
    await invoke.call({actingId:'',scanning:false}, {confirmAidPublicity:()=>assert.fail('ineligible record submitted')},
      {error:value=>{message=value}}, row)
    assert.match(message,/复核|公示期/)
  }
})
