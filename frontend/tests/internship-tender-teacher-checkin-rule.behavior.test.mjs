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
  Object.defineProperty(vm,'reminderTimeError',{get:()=>component.computed.reminderTimeError.call(vm)})
  return vm
}

test('周报零字数配置回填与提交保持一致，空值使用默认字数',()=>{
  const vm=page();vm.fillStructured({rules:{weeklyReport:{minWordCount:0}}})
  assert.equal(vm.rulesForm.weeklyReport.minWordCount,0)
  assert.equal(vm.buildRulesFromForm().weeklyReport.minWordCount,0)
  vm.rulesForm.weeklyReport.minWordCount=null
  assert.equal(vm.buildRulesFromForm().weeklyReport.minWordCount,30)
})

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

test('当天未签提醒时间可留空，保留午夜配置并拒绝错误时刻',()=>{
  const vm=page();assert.equal(vm.buildRulesFromForm().checkin.reminderTime,null)
  vm.fillStructured({rules:{checkin:{reminderTime:'00:00'}}})
  assert.equal(vm.reminderTimeError,'');assert.equal(vm.buildRulesFromForm().checkin.reminderTime,'00:00')
  vm.rulesForm.checkin.reminderTime='25:70';assert.ok(vm.reminderTimeError)
  vm.rulesForm.checkin.reminderTime='';assert.equal(vm.reminderTimeError,'')
})
