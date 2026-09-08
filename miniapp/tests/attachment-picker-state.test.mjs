import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
const source=fs.readFileSync(new URL('../src/components/MobileAttachmentPicker.vue',import.meta.url),'utf8')
const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'')
function make(sdk) {
  const scope=effectScope(), events=[], timers=[], unmount=[]
  const props=reactive({fileIds:[],bizPurpose:'FUNDING',disabled:false,maxCount:5,maxSizeMb:10,required:false})
  const emit=(name,value)=>{events.push({name,value}); if(name==='update:fileIds') props.fileIds=value}
  const vm=scope.run(()=>new Function('computed','onUnmounted','ref','watch','fileSdk','defineProps','defineEmits','setTimeout','clearTimeout',script+';return {pick,remove,files,ready,uploading}')(computed,fn=>unmount.push(fn),ref,watch,sdk,()=>props,()=>emit,fn=>{timers.push(fn);return timers.length},()=>{}))
  return {...vm,props,events,timers,dispose(){unmount.forEach(fn=>fn());scope.stop()}}
}

test('file chooser and upload block submission, successful parent reset clears visible files',async()=>{
  let choose,upload
  const vm=make({choose:()=>new Promise(r=>{choose=r}),upload:()=>new Promise(r=>{upload=r})})
  try {
    const picking=vm.pick(); assert.equal(vm.ready.value,false)
    assert.equal(vm.events.filter(x=>x.name==='update:ready').at(-1).value,false)
    choose({size:10}); await nextTick()
    upload({fileId:'1',fileName:'proof.pdf',readyForBusiness:true,scanStatus:'CLEAN'})
    await picking; await nextTick(); assert.equal(vm.ready.value,true); assert.equal(vm.files.value.length,1)
    vm.props.fileIds=[]; await nextTick(); assert.equal(vm.files.value.length,0)
    assert.equal(vm.ready.value,true)
  } finally {vm.dispose()}
})

test('scan response arriving after parent reset cannot resurrect already submitted files',async()=>{
  let scan
  const vm=make({choose:async()=>({size:10}),upload:async()=>({fileId:'1',readyForBusiness:false,scanStatus:'PENDING'}),metadata:()=>new Promise(r=>{scan=r})})
  try {
    await vm.pick(); await nextTick(); const poll=vm.timers[0]()
    vm.props.fileIds=[]; await nextTick()
    scan({fileId:'1',readyForBusiness:true,scanStatus:'CLEAN'});await poll;await nextTick()
    assert.equal(vm.files.value.length,0);assert.deepEqual([...vm.props.fileIds],[])
  } finally {vm.dispose()}
})

test('restored IDs remain unready until authorized metadata arrives; disabled removal is ignored',async()=>{
  let resolve
  const vm=make({metadata:()=>new Promise(r=>{resolve=r})})
  try {
    vm.props.fileIds=['42'];await nextTick();assert.equal(vm.ready.value,false)
    resolve({fileId:'42',readyForBusiness:true,scanStatus:'CLEAN'});await nextTick();await nextTick()
    vm.props.disabled=true;vm.remove(vm.files.value[0]);assert.equal(vm.files.value.length,1)
  } finally {vm.dispose()}
})
