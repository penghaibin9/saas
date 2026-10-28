import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(metadata) {
  const source=fs.readFileSync(new URL('../src/modules/system/SystemAttachments.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const props={modelValue:['old'],limit:20},events=[]
  const vm=new Function('ref','watch','onBeforeUnmount','defineProps','defineEmits','fileSdk',script+
    '\nreturn {load,uploadStarted,uploadCancelled,uploadFailed,uploaded}')(
    value=>({value}),()=>{},()=>{},()=>props,()=>((...args)=>events.push(args)),{metadata})
  return {vm,props,events,lastReady:()=>events.filter(e=>e[0]==='ready').at(-1)?.[1]}
}

test('旧附件读取完成不得在新附件上传中解锁保存，取消后恢复',async()=>{
  let resolve
  const p=page(()=>new Promise(done=>{resolve=done}))
  const loading=p.vm.load();p.vm.uploadStarted()
  resolve({readyForBusiness:true});await loading
  assert.equal(p.lastReady(),false)
  p.vm.uploadCancelled();assert.equal(p.lastReady(),true)
})

test('上传完成仍需新附件元数据确认，检查失败不得保存',async()=>{
  const p=page(async id=>({readyForBusiness:id==='old'}))
  await p.vm.load();assert.equal(p.lastReady(),true)
  p.vm.uploadStarted();p.vm.uploaded({fileId:'new'})
  assert.equal(p.lastReady(),false)
  p.props.modelValue=p.events.find(e=>e[0]==='update:modelValue')[1]
  await p.vm.load();assert.equal(p.lastReady(),false)
})
