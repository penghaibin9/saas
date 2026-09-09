import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/teacher/affairs/index.vue',import.meta.url),'utf8').replaceAll('\r','')
function method(name,next) {
  const start=source.indexOf(`    ${name}`), end=source.indexOf(`\n    ${next}`,start)
  assert.ok(start>=0 && end>start)
  return new Function('affairsContractApi','normalizeError','toast','uni',source.slice(source.indexOf('{',start)+1,end).replace(/\n {4}\},$/,''))
}
test('teacher material deep link filters on the server before paging',async()=>{
  const load=method('loadMaterials(showToast = true, reset = true)','loadBatches')
  // The extracted defaults are passed as locals so the actual body is exercised.
  const body=load.toString().slice(load.toString().indexOf('{')+1,-1)
  const run=new Function('affairsContractApi','normalizeError','toast','uni','showToast','reset',body)
  const vm={focusMaterialId:'89',leaveContext:{bizType:'AID',bizId:'45'},materialPage:4,selectedMaterialIds:[],scrollToMaterial(){}}
  let sent
  await run.call(vm,{getMaterialRequirements:async(...args)=>{sent=args;return {items:[{requirementId:'89'}],total:1}}},e=>({text:e.message}),()=>{},{},false,true)
  assert.deepEqual(sent,['',1,20,{bizType:'AID',bizId:'45',requirementId:'89'}])
  assert.equal(vm.materialHasMore,false)
  assert.equal(vm.materials[0].requirementId,'89')
})
test('material review reloads the workbench as well as the material list',async()=>{
  const start=source.indexOf('    reviewMaterial(item, action)'),end=source.indexOf('\n    createReminderBatch',start)
  const review=new Function('affairsContractApi','normalizeError','toast','uni','item','action',source.slice(source.indexOf('{',start)+1,end).replace(/\n {4}\},$/,''))
  let finished, refreshed=0
  const done=new Promise(resolve=>{finished=resolve})
  const vm={materialBusy:'',returnReason:'请补充具体收入情况',cancelReturn(){},load(){refreshed++;finished();return Promise.resolve()}}
  review.call(vm,{reviewMaterialRequirement:async()=>({status:'RETURNED'})},e=>({text:e.message}),()=>{},{},{requirementId:'89',version:2},'RETURN')
  await done
  assert.equal(refreshed,1)
})
