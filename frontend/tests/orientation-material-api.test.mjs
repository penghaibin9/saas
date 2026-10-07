import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/modules/orientation/api/orientation.api.js', import.meta.url), 'utf8')
const methods = source.slice(source.indexOf('export async function approveOrientationMaterial'), source.indexOf('/* ---------------- 宿舍入住'))
  .replaceAll('export async function', 'async function')

function setup(handler = async () => ({ code: 0 })) {
  const calls = []
  const api = new Function('callData', 'request', 'fail', 'envelope', `${methods}; return {batchReviewOrientationMaterials}`)(
    fn => fn(), async (url, options) => { calls.push({ url, ...options }); return handler(calls.length, options) },
    message => ({ code: 1, message }), data => ({ code: 0, data })
  )
  return { ...api, calls }
}

test('batch material review sends original versions and stops at the first conflict', async () => {
  const api = setup(async n => n === 2 ? {code:409,message:'已有更新'} : {code:0})
  const result = await api.batchReviewOrientationMaterials([{id:'1',version:4},{id:'2',version:7},{id:'3',version:1}],{pass:true})
  assert.equal(api.calls.length,2)
  assert.deepEqual(api.calls.map(call=>call.body.expectedVersion),[4,7])
  assert.deepEqual(result.data,{completedIds:['1'],failedId:'2'})
  assert.match(result.message,/已完成 1 份/)
})

test('batch review validates all selected versions before writing any material', async () => {
  for (const version of [undefined,-1,'2']) {
    const api = setup()
    const result = await api.batchReviewOrientationMaterials([{id:'1',version:0},{id:'2',version}],{pass:true})
    assert.notEqual(result.code,0)
    assert.equal(api.calls.length,0)
  }
})

test('batch return keeps reason, reports exact completion, and stops if context changed', async () => {
  const api = setup()
  const materials = [{id:'9007199254740993',version:0},{id:'2',version:1}]
  const complete = await api.batchReviewOrientationMaterials(materials,{pass:false,reason:'请重新提供清晰材料'})
  assert.equal(complete.data.count,2)
  assert.deepEqual(complete.data.completedIds,materials.map(row=>row.id))
  assert.ok(api.calls.every(call=>call.body.reason==='请重新提供清晰材料'))
  const stopped = setup()
  const partial = await stopped.batchReviewOrientationMaterials(materials,{pass:true,shouldContinue:()=>stopped.calls.length===0})
  assert.equal(stopped.calls.length,1)
  assert.deepEqual(partial.data.completedIds,[materials[0].id])
})
