import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source=readFileSync(new URL('../src/modules/studentAffairs/pickerAdapters.js',import.meta.url),'utf8')
  .replace(/^import .+$/gm,'').replace(/export /g,'')
function picker(api) {
  return new Function('studentAffairsApi','createOrgPickerAdapters','createTeacherPickerAdapter','safeEnumLabel',source+'\nreturn studentAffairsPickerAdapters.aidBatch')(
    api,()=>({}),()=>({}),({value,dictionary})=>dictionary[value]||value)
}
test('shared batch picker searches all server batches and resolves a selected historical id exactly',async()=>{
  const sent=[]
  const p=picker({getAidBatches:async params=>{sent.push(params);return {code:0,data:{items:[{batchId:'105',batchName:'历史认定',schoolYear:'2021-2022',status:'OPEN'}]}}},
    getAidBatch:async id=>{sent.push(id);return {code:0,data:{batchId:id,batchName:'原批次',status:'OPEN'}}}})
  const result=await p.search('历史')
  assert.equal(sent[0].keyword,'历史')
  assert.equal(result[0].value,'105')
  assert.equal(result[0].raw.schoolYear,'2021-2022')
  assert.equal((await p.resolve('2')).label,'原批次')
  assert.equal(sent[1],'2')
})
test('shared batch picker never treats a denied resolution as another batch',async()=>{
  const p=picker({getAidBatch:async()=>({code:403,message:'批次不可见'})})
  await assert.rejects(p.resolve('2'),/批次不可见/)
})
