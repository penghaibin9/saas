import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/pages/student/affairs/dorm.vue',import.meta.url),'utf8')
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','return')
const page=new Function('createSubmitLock',script)(()=>({}))
function view(){const vm={...page.data(),...page.methods};for(const [k,fn] of Object.entries(page.computed))Object.defineProperty(vm,k,{get:fn.bind(vm)});return vm}
test('failed transfer history cannot open or submit another transfer',()=>{
 const vm=view();vm.cfg={hasBed:true};vm.transferError='暂不可用';vm.sel.bed='5'
 assert.equal(vm.canChoose,false)
 vm.confirm()
 assert.equal(vm.confirmDlg.visible,false)
 vm.transferError=''
 assert.equal(vm.canChoose,true)
 vm.transfers=[{status:'SUBMITTED'}]
 assert.equal(vm.canChoose,false)
})
test('returning to the dorm page refreshes teacher changes',()=>{
 let loaded=0
 page.onShow.call({load(){loaded++}})
 assert.equal(loaded,1)
})

test('returning from the file picker does not invalidate an in-flight submission', () => {
 let loaded = 0
 page.onShow.call({ submitting: true, load() { loaded++ } })
 assert.equal(loaded, 0)
})

test('failed stay and rectification queries expose errors, not empty success', async () => {
 const c = new Function('createSubmitLock', 'studentApi', 'affairsContractApi', 'normalizeError', 'currentSessionGeneration', script)(()=>({}),
  {getMyDorm:async()=>({hasBed:false})}, {
   getMyDormTransfers:async()=>({items:[]}),
   getMyDormStays:async()=>{throw Error('住宿服务暂不可用')},
   getMyDormRectifications:async()=>{throw Error('整改服务暂不可用')}
  }, e=>({text:e.message}), () => 1)
 const vm={...c.data(),...c.methods}
 await vm.load()
 assert.equal(vm.state,'ready')
 assert.equal(vm.stayError,'住宿服务暂不可用')
 assert.equal(vm.rectError,'整改服务暂不可用')
 assert.match(source,/v-if="!rectError && !rectifications.length"/)
 assert.match(source,/v-if="!stayError && !stays.length"/)
})
