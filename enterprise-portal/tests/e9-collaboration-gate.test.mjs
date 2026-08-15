import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const store=fs.readFileSync(new URL('../src/stores/enterpriseContext.js',import.meta.url),'utf8')
const students=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')
const evaluations=fs.readFileSync(new URL('../src/views/EvaluationTaskListView.vue',import.meta.url),'utf8')

test('E9 collaboration stays fail closed unless server capability and batch id are both present',()=>{
  assert.match(store,/capabilities:\{recruitmentWrite:false,internshipCollab:false\}/)
  assert.match(store,/internshipCollab:authContext\?\.capabilities\?\.internshipCollab===true/)
  assert.match(store,/internshipCollabReady:\(state\)=>state\.contextReady&&state\.capabilities\?\.internshipCollab===true&&Number\(state\.campaign\?\.batchId\)>0/)
  assert.match(store,/campaign\.batchId=authContext\.batchId/)
  assert.doesNotMatch(store,/internshipCollab\s*:\s*true/)
})

test('E9 pages issue zero collaboration requests when the capability is not ready',()=>{
  for(const page of [students,evaluations]){
    const guard=page.indexOf('if(!collabReady.value)')
    const call=page.indexOf('enterpriseInternshipApi.',guard)
    assert.ok(guard>=0,'page must contain collaboration guard')
    assert.ok(call>guard,'network call must occur after collaboration guard')
  }
})
