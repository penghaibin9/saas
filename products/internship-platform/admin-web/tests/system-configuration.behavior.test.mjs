import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

test('学校配置保存守住冲突、附件就绪及只读权限，切换分类不沿用旧附件阻塞',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/system/ConfigurationWorkspace.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const props={category:'brand'}
  let categoryChanged,writes=0,editable=true,submitted
  const reply={version:1,reminderText:'输入保留',responsibleName:'合成服务承办人',responsibleUserId:'123',responsibleValid:true}
  const vm=new Function('ref','computed','watch','onBeforeUnmount','defineProps','areaPackage','statusOptions','ElLoading','get','save','matchPermission','getPermissionPatterns','fileSdk',script+
    '\nreturn {form,conflict,filesReady,responsibleName,invalidResponsibleId,submit,load}')(
    value=>({value}),getter=>({get value(){return getter()}}),(getter,callback)=>{categoryChanged=callback;callback()},()=>{},()=>props,
    {version:'test'},{enterpriseIndustry:[]},{directive:{}},async()=>reply,async(_,body)=>{writes++;submitted=body},()=>editable,()=>[],{})
  await vm.load()
  vm.conflict.value={version:2};await vm.submit();assert.equal(writes,0)
  assert.equal(vm.form.value.reminderText,'输入保留')
  assert.equal(vm.responsibleName.value,'合成服务承办人')
  assert.equal(Object.hasOwn(vm.form.value,'responsibleName'),false)
  assert.equal(vm.invalidResponsibleId.value,'')
  assert.equal(Object.hasOwn(vm.form.value,'responsibleValid'),false)
  vm.conflict.value=null;vm.filesReady.value=false;await vm.submit();assert.equal(writes,0)
  props.category='notification';categoryChanged();await vm.load()
  assert.equal(vm.filesReady.value,true)
  editable=false;await vm.submit();assert.equal(writes,0)
  reply.responsibleValid=false;reply.responsibleName='';await vm.load()
  assert.equal(vm.invalidResponsibleId.value,'123');assert.equal(vm.responsibleName.value,'')
  editable=true;await vm.submit();assert.equal(writes,1)
  assert.equal(Object.hasOwn(submitted,'responsibleName'),false)
  assert.equal(Object.hasOwn(submitted,'responsibleValid'),false)
  props.category='dictionary';reply.standardReferences=[{kind:'major',source:'合成目录',edition:'第一版'}]
  await vm.load()
  assert.equal(vm.form.value.standardReferences.length,4)
  assert.equal(vm.form.value.standardReferences.find(row=>row.kind==='major').edition,'第一版')
  const area=vm.form.value.standardReferences.find(row=>row.kind==='area')
  assert.equal(area.source,'')
  area.source='实际所用地区数据包'
  await vm.submit();assert.equal(writes,1)
  assert.equal(area.source,'实际所用地区数据包')
  area.edition='合成第二版'
  await vm.submit()
  assert.deepEqual(submitted.standardReferences.find(row=>row.kind==='area'),
    {kind:'area',source:'实际所用地区数据包',edition:'合成第二版'})
})

test('校徽预览更换、读取失败及页面离开时释放旧图片，迟到响应不覆盖新选择',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/system/ConfigurationWorkspace.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const pending=[],released=[];let unmount
  const vm=new Function('ref','computed','watch','onBeforeUnmount','defineProps','areaPackage','statusOptions','ElLoading','get','save','matchPermission','getPermissionPatterns','fileSdk','URL',script+
    '\nreturn {form,logoUrl,logoError,loadLogo}')(
    value=>({value}),getter=>({get value(){return getter()}}),()=>{},callback=>{unmount=callback},()=>({category:'brand'}),
    {version:'test'},{enterpriseIndustry:[]},{directive:{}},()=>{},()=>{},()=>true,()=>[],
    {blob:id=>new Promise((resolve,reject)=>pending.push({id,resolve,reject}))},
    {createObjectURL:blob=>'blob:'+blob,revokeObjectURL:url=>released.push(url)})
  vm.form.value={logoFileId:'1'};const old=vm.loadLogo()
  vm.form.value={logoFileId:'2'};const current=vm.loadLogo()
  pending[1].resolve('second');await current;assert.equal(vm.logoUrl.value,'blob:second')
  pending[0].resolve('first');await old;assert.equal(vm.logoUrl.value,'blob:second')
  vm.form.value={logoFileId:'3'};const failed=vm.loadLogo();assert.equal(vm.logoUrl.value,'')
  assert.deepEqual(released,['blob:second']);pending[2].reject(new Error('denied'));await failed
  assert.match(vm.logoError.value,/暂时无法预览/)
  vm.form.value={logoFileId:'4'};const leaving=vm.loadLogo();unmount();pending[3].resolve('fourth');await leaving
  assert.equal(vm.logoUrl.value,'');assert.equal(vm.logoError.value,'')
})
