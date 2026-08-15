import test from 'node:test'
import assert from 'node:assert/strict'
import { enterpriseInternshipApi } from '../src/services/enterpriseInternshipApi.js'

test('every unfrozen A01 facade rejects locally without issuing a network request', async () => {
  const originalFetch=globalThis.fetch
  let fetchCalls=0
  globalThis.fetch=async()=>{fetchCalls+=1;throw new Error('network must not be reached')}
  try{
    const calls=[
      ['dashboard',()=>enterpriseInternshipApi.dashboard()],
      ['campaigns',()=>enterpriseInternshipApi.campaigns()],
      ['company',()=>enterpriseInternshipApi.company()],
      ['updateCompany',()=>enterpriseInternshipApi.updateCompany({shortName:'x'})],
      ['positions',()=>enterpriseInternshipApi.positions({page:1})],
      ['position',()=>enterpriseInternshipApi.position('1')],
      ['createPosition',()=>enterpriseInternshipApi.createPosition({title:'x'})],
      ['updatePosition',()=>enterpriseInternshipApi.updatePosition('1',{title:'x'})],
      ['submitPosition',()=>enterpriseInternshipApi.submitPosition('1')],
      ['withdrawPosition',()=>enterpriseInternshipApi.withdrawPosition('1')],
      ['applications',()=>enterpriseInternshipApi.applications({page:1})],
      ['application',()=>enterpriseInternshipApi.application('1')],
      ['resumePdf',()=>enterpriseInternshipApi.resumePdf('1')],
      ['revealContact',()=>enterpriseInternshipApi.revealContact('1')],
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
