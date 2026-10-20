import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source=readFileSync(new URL('../src/pages/student/affairs/index.vue',import.meta.url),'utf8')
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'').replace('export default','return')
function make(api,sdk) {
  const component=new Function('affairsContractApi','fileSdk','normalizeError','toast','go','currentSessionGeneration',script)(api,sdk,e=>({text:e.message}),()=>{},()=>{},()=>1)
  return {...component.data(),...component.methods,loadMaterials:async()=>{}}
}
test('mobile scanning retries keep one upload and submit once with the original version',async()=>{
  let uploads=0, submissions=0, ready=false, sent
  const vm=make({uploadMaterialFile:async()=>{uploads++;return {fileId:'77'}},submitMaterialVersion:async(...args)=>{submissions++;sent=args}},
    {metadata:async fileId=>({fileId,readyForBusiness:ready,status:ready?'AVAILABLE':'QUARANTINED',scanStatus:ready?'CLEAN':'PENDING'})})
  vm.selectedFiles['1']={path:'/proof.pdf',name:'proof.pdf'};vm.materialNotes['1']='补交说明'
  const item={requirementId:'1',version:8}
  await vm.submitMaterial(item);await vm.submitMaterial(item)
  assert.equal(uploads,1);assert.equal(submissions,0);assert.match(vm.materialFileHint(vm.uploadedMaterials['1']),/无需重复上传/)
  ready=true;await vm.submitMaterial(item)
  assert.equal(uploads,1);assert.equal(submissions,1);assert.deepEqual(sent,['1','77','补交说明',8])
  assert.equal(vm.selectedFiles['1'],undefined);assert.equal(vm.materialBusy,'')
})
test('mobile failure retains file and note; unavailable metadata never causes submission',async()=>{
  for(const status of ['PENDING','ERROR','INFECTED',undefined]){
    let submissions=0
    const vm=make({uploadMaterialFile:async()=>({fileId:'1'}),submitMaterialVersion:async()=>{submissions++}},
      {metadata:async()=>({fileId:'1',scanStatus:status})})
    vm.selectedFiles['1']={path:'/proof.pdf'};vm.materialNotes['1']='保留说明'
    await vm.submitMaterial({requirementId:'1',version:1})
    assert.equal(submissions,0);assert.equal(vm.materialNotes['1'],'保留说明');assert.equal(vm.materialBusy,'')
  }
  const vm=make({uploadMaterialFile:async()=>({fileId:'1'}),submitMaterialVersion:async()=>{throw Error('版本已更新，请刷新')}},
    {metadata:async()=>({fileId:'1',readyForBusiness:true})})
  vm.selectedFiles['1']={path:'/proof.pdf'};await vm.submitMaterial({requirementId:'1',version:1})
  assert.match(vm.materialNotices['1'],/请刷新/);assert.ok(vm.selectedFiles['1']);assert.equal(vm.materialBusy,'')
})

test('mobile file selection cannot change a material while a submission is running',()=>{
  const vm=make({}, {})
  vm.materialBusy='1';vm.selectedFiles['1']={path:'/original.pdf'}
  // No native chooser is available in this harness: a blocked click must return before calling it.
  vm.chooseMaterial({requirementId:'1'})
  vm.chooseMaterial({requirementId:'2'})
  assert.deepEqual(vm.selectedFiles,{'1':{path:'/original.pdf'}})
})
