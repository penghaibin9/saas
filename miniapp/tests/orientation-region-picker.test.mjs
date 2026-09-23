import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { areaList } from '@vant/area-data'
const source = fs.readFileSync(new URL('../src/components/MobileRegionPicker.vue', import.meta.url),'utf8')
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','return')
const component=new Function('areaList',script)(areaList)
function view(value='') {
  const vm={...component.data(), modelValue:value, events:[], $emit(key,value){this.events.push([key,value]); if(key==='update:modelValue'){this.modelValue=value; component.watch.modelValue.handler.call(this,value)}}}
  for(const [key,fn] of Object.entries(component.computed)) Object.defineProperty(vm,key,{get:fn.bind(vm)})
  for(const [key,fn] of Object.entries(component.methods)) vm[key]=fn.bind(vm)
  component.watch.modelValue.handler.call(vm,value)
  return vm
}
test('web region selection keeps province and city while clearing old county',()=>{
  const vm=view('湖南省 长沙市 岳麓区')
  vm.chooseProvince('330000')
  assert.equal(vm.provinceCode,'330000'); assert.equal(vm.cityCode,''); assert.equal(vm.modelValue,'')
  vm.chooseCity('330100'); vm.chooseCounty('330106')
  assert.equal(vm.modelValue,'浙江省 杭州市 西湖区')
  assert.equal(vm.events.at(-1)[1].countyCode,'330106')
})
test('municipality label round trips and legacy free text is retained',()=>{
  const vm=view('北京市 朝阳区')
  assert.equal(vm.cityCode,'110100'); assert.equal(vm.countyCode,'110105')
  assert.equal(view('历史生源地').modelValue,'历史生源地')
})
