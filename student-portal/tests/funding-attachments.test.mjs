import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { computed, effectScope, reactive, ref, watch } from 'vue'
const source=fs.readFileSync(new URL('../src/views/affairs/FundingAttachments.vue',import.meta.url),'utf8')
const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'')
function make(sdk) {
  const scope=effectScope(),events=[],unmount=[],props=reactive({disabled:false,initialFiles:[]})
  const defineProps = definitions => {
    for (const [key, definition] of Object.entries(definitions)) {
      if (!(key in props) && 'default' in definition) props[key] = typeof definition.default === 'function' ? definition.default() : definition.default
    }
    return props
  }
  const vm=scope.run(()=>new Function('computed','onBeforeUnmount','ref','watch','fileSdk','defineProps','defineEmits',script+';return {choose,upload,check,remove,files,uploading,notice}')(computed,fn=>unmount.push(fn),ref,watch,sdk,defineProps,()=>((_name,state)=>events.push(state))))
  return {...vm,props,events,dispose(){unmount.forEach(fn=>fn());scope.stop()}}
}

test('scan checks reuse uploaded ID and preserve failures, removing last draft restores readiness',async()=>{
  let uploads=0,checks=0
  const vm=make({upload:async()=>{uploads++;return {fileId:'1',readyForBusiness:false,statusText:'等待安全扫描'}},metadata:async()=>{checks++;if(checks===1)throw Error('offline');return {fileId:'1',readyForBusiness:true}}})
  try {
    await vm.choose({target:{files:[{name:'proof.pdf',size:10}],value:'proof'}})
    assert.equal(vm.events.at(-1).ready,false)
    await vm.check(vm.files.value[0]);assert.match(vm.files.value[0].error,/offline/)
    await vm.check(vm.files.value[0]);assert.equal(vm.events.at(-1).ready,true)
    assert.equal(uploads,1);assert.deepEqual(vm.events.at(-1).fileIds,['1'])
    vm.remove(vm.files.value[0]);assert.equal(vm.events.at(-1).hasDraft,false)
  } finally {vm.dispose()}
})

test('upload in flight blocks submit/removal and file limits reject without partial uploads',async()=>{
  let finish,calls=0
  const vm=make({upload:()=>{calls++;return new Promise(r=>{finish=r})}})
  try {
    await vm.choose({target:{files:Array.from({length:6},()=>({name:'x',size:1})),value:''}})
    assert.equal(calls,0);assert.equal(vm.files.value.length,0)
    const work=vm.choose({target:{files:[{name:'x.pdf',size:1}],value:''}})
    assert.equal(vm.events.at(-1).ready,false);assert.equal(vm.events.at(-1).busy,true)
    vm.remove(vm.files.value[0]);assert.equal(vm.files.value.length,1)
    finish({fileId:'2',readyForBusiness:true});await work
    assert.equal(vm.events.at(-1).ready,true)
  } finally {vm.dispose()}
})
