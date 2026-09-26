import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source = fs.readFileSync(new URL('../src/pages/student/orientation/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default','return')
const component = new Function('go', script)(() => {})
function view(stage) {
 const vm={...component.data(),o:{stage,steps:[{key:'INFO',status:'TODO',title:'信息核对'}],selfService:{available:true},identity:{}}}
 for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:fn.bind(vm)})
 return vm
}
test('paused admission gives a specific outcome and no student submission action',()=>{
 for(const [stage,title] of [['DEFERRED','已延期报到'],['NO_SHOW','已登记未到校'],['CANCELLED','已取消入学']]){
  const vm=view(stage)
  assert.equal(vm.arrivalHold.title,title)
  assert.equal(vm.nextAction.title,title)
  assert.equal(vm.nextAction.path,'')
 }
})
test('resumed admission restores the normal next action',()=>{
 const vm=view('ADMITTED')
 assert.equal(vm.arrivalHold,null)
 assert.equal(vm.nextAction.path,'/pages/student/orientation/collect/index')
})

