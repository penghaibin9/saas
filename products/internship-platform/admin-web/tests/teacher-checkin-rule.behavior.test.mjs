import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

function page(){
  const source=fs.readFileSync(new URL('../src/modules/internship/views/BatchFormView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*\r?\n/gm,'').replace('export default','return')
  const scope=Object.fromEntries(['ModulePageShell','LoadingState','ErrorState','AppButton','AppInlineAlert','AppForm','AppFormItem','AppTextInput','AppNumberInput','AppTextarea','AppSubmitBar','AppDatePicker','AppTimeline','AppDescriptionList','AppSelect','AppRadioGroup'].map(key=>[key,{}]))
  const component=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...component.data(),readonly:false}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  Object.defineProperty(vm,'teacherLocationError',{get:()=>component.computed.teacherLocationError.call(vm)})
  return vm
}

test('学校配置地点保留零坐标及国际坐标类型，回填不修改原详情',()=>{
  const vm=page(),site={name:'合成境外地点',centerLat:0,centerLng:0,radiusM:300,coordinateSystem:'WGS84'}
  vm.fillStructured({rules:{teacherCheckin:{maxAccuracyM:100,locations:[site]}}})
  assert.equal(vm.teacherLocationError,'');assert.deepEqual(vm.buildRulesFromForm().teacherCheckin,{maxAccuracyM:100,locations:[site]})
  vm.rulesForm.teacherCheckin.locations[0].name='调整后';assert.equal(site.name,'合成境外地点')
})

test('学校地点缺坐标、空名称、重复名称及错误半径会定位为中文错误',()=>{
  const site={name:'合成地点',centerLat:0,centerLng:0,radiusM:300,coordinateSystem:'WGS84'}
  for(const change of [{centerLat:null},{name:''},{radiusM:0},{coordinateSystem:'UNKNOWN'}]){
    const vm=page();vm.rulesForm.teacherCheckin.locations=[{...site,...change}];assert.ok(vm.teacherLocationError)
  }
  const vm=page();vm.rulesForm.teacherCheckin.locations=[{...site},{...site}];assert.ok(vm.teacherLocationError.includes('重复'))
})

test('学校地点添加移除保护只读模式及数量上限',()=>{
  const vm=page();vm.addTeacherLocation();assert.equal(vm.rulesForm.teacherCheckin.locations.length,1)
  vm.readonly=true;vm.addTeacherLocation();vm.removeTeacherLocation(0);assert.equal(vm.rulesForm.teacherCheckin.locations.length,1)
  vm.readonly=false;vm.removeTeacherLocation(0);assert.equal(vm.rulesForm.teacherCheckin.locations.length,0)
  vm.rulesForm.teacherCheckin.locations=Array.from({length:50},()=>({}));vm.addTeacherLocation();assert.equal(vm.rulesForm.teacherCheckin.locations.length,50)
})
