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

test('external form clear removes the previous region from every selector', () => {
  const vm = view('浙江省 杭州市 西湖区')
  assert.equal(vm.countyCode, '330106')
  vm.modelValue = ''
  component.watch.modelValue.handler.call(vm, '')
  assert.equal(vm.provinceCode, '')
  assert.equal(vm.cityCode, '')
  assert.equal(vm.countyCode, '')
  assert.deepEqual(vm.events, [])
})

test('a completed selection can be cleared externally without preserving an internal draft', () => {
  const vm = view('湖南省 长沙市 岳麓区')
  vm.chooseProvince('330000'); vm.chooseCity('330100'); vm.chooseCounty('330106')
  assert.equal(vm.modelValue, '浙江省 杭州市 西湖区')
  vm.modelValue = ''
  component.watch.modelValue.handler.call(vm, '')
  assert.equal(vm.provinceCode + vm.cityCode + vm.countyCode, '')
})

test('disabled region selection never changes a value or emits a native confirmation', () => {
  const vm = view('浙江省 杭州市 西湖区')
  vm.disabled = true
  vm.chooseProvince('430000'); vm.chooseCity('430100'); vm.chooseCounty('430104')
  vm.onConfirm({ detail: { value: ['湖南省', '长沙市', '岳麓区'], code: ['430000', '430100', '430104'] } })
  assert.equal(vm.modelValue, '浙江省 杭州市 西湖区')
  assert.equal(vm.countyCode, '330106')
  assert.deepEqual(vm.events, [])
})

import { createRenderer, h, nextTick, ref } from 'vue'

test('Vue prop updates distinguish internal cascading edits from an external clear', async () => {
  const renderer = createRenderer({
    createElement: tag => ({ tag, children: [] }), createText: text => ({ text }), createComment: text => ({ text }),
    insert(child, parent) { child.parent = parent; (parent.children ||= []).push(child) }, remove() {},
    parentNode: node => node.parent, nextSibling: () => null, patchProp() {},
    setText(node, text) { node.text = text }, setElementText(node, text) { node.text = text }
  })
  const model = ref('浙江省 杭州市 西湖区')
  const definition = { ...component, render: () => null }
  let region
  const app = renderer.createApp({ setup: () => () => h(definition, {
    modelValue: model.value, 'onUpdate:modelValue': value => { model.value = value }, ref: value => { region = value }
  }) })
  app.mount({ children: [] })
  try {
    region.chooseProvince('430000'); await nextTick()
    assert.equal(model.value, ''); assert.equal(region.provinceCode, '430000')
    region.chooseCity('430100'); await nextTick()
    assert.equal(region.cityCode, '430100')
    region.chooseCounty('430104'); await nextTick()
    assert.equal(region.countyCode, '430104'); assert.notEqual(model.value, '')
    model.value = ''; await nextTick()
    assert.equal(region.provinceCode + region.cityCode + region.countyCode, '')
  } finally { app.unmount() }
})
