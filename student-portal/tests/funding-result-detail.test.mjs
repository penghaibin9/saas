import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { ref } from 'vue'

for (const [client,path] of [['PC','../src/views/affairs/FundingApplicationDetail.vue'],['mini','../../miniapp/src/components/MobileFundingDetail.vue']]) {
  const source=fs.readFileSync(new URL(path,import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'')
  function make(api) {
    const props={applicationId:'1'}, dispose=[]
    const vm=new Function('ref','onMounted','onBeforeUnmount','onUnmounted','watch','defineProps','defineEmits','useRouter','portalApi','studentApi','normalizeError',script+';return {detail,loading,error,load,money}')(ref,()=>{},fn=>dispose.push(fn),fn=>dispose.push(fn),()=>{},()=>props,()=>()=>{},()=>({push(){}}),{affairsFundingDetail:api},{getFundingDetail:api},e=>({text:e.message}))
    return {...vm,props,dispose:()=>dispose.forEach(fn=>fn())}
  }
  test(`${client} result ignores an older response and clears old content during another application load`,async()=>{
    let first
    const vm=make(id=>id==='1'?new Promise(r=>{first=r}):Promise.resolve({applicationId:id,status:'GRANTED'}))
    const old=vm.load(); vm.props.applicationId='2'; await vm.load()
    first({applicationId:'1',status:'RETURNED'}); await old
    assert.equal(vm.detail.value.applicationId,'2'); assert.equal(vm.loading.value,false)
  })
  test(`${client} result fails closed on a mismatched application and does not invent an approved amount`,async()=>{
    const vm=make(async()=>({applicationId:'other'})); await vm.load()
    assert.equal(vm.detail.value,null); assert.match(vm.error.value,/不匹配/)
    assert.equal(vm.money(null),'尚未确定'); assert.equal(vm.money('0.00'),'0.00 元')
  })
  test(`${client} result ignores completion after closing the view`,async()=>{
    let finish
    const vm=make(()=>new Promise(r=>{finish=r})); const work=vm.load(); vm.dispose()
    finish({applicationId:'1'}); await work; assert.equal(vm.detail.value,null)
  })
}
