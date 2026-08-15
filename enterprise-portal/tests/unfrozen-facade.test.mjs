import test from 'node:test'
import assert from 'node:assert/strict'
import { enterpriseInternshipApi } from '../src/services/enterpriseInternshipApi.js'

test('only still-unfrozen resume PDF rejects locally without issuing a network request', async () => {
  const originalFetch=globalThis.fetch
  let fetchCalls=0
  globalThis.fetch=async()=>{fetchCalls+=1;throw new Error('network must not be reached')}
  try{
    await assert.rejects(()=>enterpriseInternshipApi.resumePdf('1'),error=>{
      assert.equal(error.code,'ENTERPRISE_FACADE_UNFROZEN')
      assert.equal(error.facade,'简历 PDF')
      return true
    })
    assert.equal(fetchCalls,0)
  }finally{
    globalThis.fetch=originalFetch
  }
})
