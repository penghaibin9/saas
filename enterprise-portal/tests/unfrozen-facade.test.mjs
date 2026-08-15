import test from 'node:test'
import assert from 'node:assert/strict'
import { enterpriseInternshipApi } from '../src/services/enterpriseInternshipApi.js'

test('only still-unfrozen E9/PDF facades reject locally without issuing a network request', async () => {
  const originalFetch=globalThis.fetch
  let fetchCalls=0
  globalThis.fetch=async()=>{fetchCalls+=1;throw new Error('network must not be reached')}
  try{
    const calls=[
      ['resumePdf',()=>enterpriseInternshipApi.resumePdf('1')],
      ['internshipStudents',()=>enterpriseInternshipApi.internshipStudents({page:1})],
      ['internshipStudent',()=>enterpriseInternshipApi.internshipStudent('1')],
      ['evaluationTasks',()=>enterpriseInternshipApi.evaluationTasks({page:1})],
      ['submitEvaluation',()=>enterpriseInternshipApi.submitEvaluation('1',{overallComment:'ok'})],
    ]
    for(const [name,call] of calls){
      await assert.rejects(call,error=>{
        assert.equal(error.code,'ENTERPRISE_FACADE_UNFROZEN',name)
        assert.ok(error.facade,name)
        return true
      })
    }
    assert.equal(fetchCalls,0)
  }finally{
    globalThis.fetch=originalFetch
  }
})
