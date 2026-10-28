import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(save,get=async()=>({items:[],catalog:[],templates:[]})) {
  const source=fs.readFileSync(new URL('../src/modules/system/RoleWorkspace.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  return new Function('ref','computed','onMounted','ElLoading','get','save','getPermissionPatterns','matchPermission',script+
    '\nreturn {form,target,conflict,memberConflict,submit,saveMember,edit,impact,impactBusy,refreshImpact,memberUser,memberImpact,memberImpactReady,members,formError,data,preset,presetMissing,presetAdditional,choosePresetPermission,readonly,saving}')(
    value=>({value}),getter=>({get value(){return getter()}}),()=>{},{directive:{}},get,save,()=>['system.role.manage'],(patterns,code)=>patterns.includes(code))
}

test('模板对照不自动改变学校配置，逐项调整只改草稿并撤回旧敏感确认',async()=>{
  let writes=0
  const vm=page(async()=>{writes++})
  vm.data.value={items:[],templates:[{code:'INTERN_MENTOR',name:'实习指导教师',permissions:['internship.leave.view','internship.student.password.reset']}],
    catalog:[{code:'internship.leave.view',name:'查看实习请假'},{code:'internship.student.password.reset',name:'受控重置学生登录密码'},{code:'system.student.view',name:'查看学生资料'}]}
  vm.form.value={baseRole:'INTERN_MENTOR',permissions:['internship.leave.view','system.student.view'],sensitiveConfirmed:true}
  assert.deepEqual(vm.presetMissing.value.map(p=>p.name),['受控重置学生登录密码'])
  assert.deepEqual(vm.presetAdditional.value.map(p=>p.name),['查看学生资料'])
  assert.deepEqual(vm.form.value.permissions,['internship.leave.view','system.student.view'])
  vm.choosePresetPermission('internship.student.password.reset',true)
  assert.equal(vm.form.value.sensitiveConfirmed,false)
  assert.equal(writes,0)
  vm.choosePresetPermission('system.student.view',false)
  assert.deepEqual(vm.form.value.permissions,['internship.leave.view','internship.student.password.reset'])
  vm.choosePresetPermission('unknown.permission',true)
  assert.equal(vm.form.value.permissions.length,2)
})

test('对照遵守只读、冲突与提交锁；切换身份类型后重算模板而非套用权限',async()=>{
  const vm=page(async()=>{})
  vm.data.value={items:[],templates:[{code:'INTERN_MENTOR',name:'指导教师',permissions:['a']},{code:'LEADER',name:'领导',permissions:['b']}],
    catalog:[{code:'a',name:'查看请假'},{code:'b',name:'查看汇总'}]}
  vm.form.value={baseRole:'INTERN_MENTOR',permissions:[]}
  for(const flag of [vm.readonly,vm.conflict,vm.saving]){
    flag.value=true;vm.choosePresetPermission('a',true);assert.deepEqual(vm.form.value.permissions,[]);flag.value=false
  }
  vm.form.value.baseRole='LEADER'
  assert.deepEqual(vm.presetMissing.value.map(p=>p.code),['b'])
  vm.choosePresetPermission('a',true);assert.deepEqual(vm.form.value.permissions,[])
  vm.choosePresetPermission('b',true);assert.deepEqual(vm.form.value.permissions,['b'])
})

test('角色保存拒绝重入；版本冲突未经明确核对不可重交',async()=>{
  let resolve,writes=0
  const vm=page(()=>{writes++;return new Promise(done=>{resolve=done})})
  vm.form.value={name:'空权限',permissions:[]}
  const pending=vm.submit();await vm.submit();assert.equal(writes,1)
  resolve({});await pending
  vm.conflict.value={version:2,current:{name:'其他编辑者'}}
  await vm.submit();assert.equal(writes,1)
  assert.equal(vm.form.value.name,'空权限')
})

test('成员保存拒绝重入并保留版本冲突下的原选择',async()=>{
  let resolve,writes=0
  const vm=page(()=>{writes++;return new Promise(done=>{resolve=done})})
  vm.target.value={id:'1',version:1}
  vm.memberUser.value='2';vm.memberImpact.value={roleId:'1',userId:'2'}
  const pending=vm.saveMember();await vm.saveMember();assert.equal(writes,1)
  resolve({});await pending
  vm.memberConflict.value={version:2,current:{name:'其他编辑者'}}
  await vm.saveMember();assert.equal(writes,1)
  assert.equal(vm.target.value.version,1)
})

test('角色影响读取期间或失败时禁止保存，另一角色不会收到旧结果',async()=>{
  let finish,writes=0
  const vm=page(async()=>{writes++},path=>path==='/roles/1/impact' ? new Promise(resolve=>{finish=resolve}) : Promise.reject(new Error('影响读取失败')))
  const first=vm.edit({id:'1',name:'原角色',permissions:[]})
  await vm.submit();assert.equal(writes,0)
  await vm.edit({id:'2',name:'当前角色',permissions:[]})
  finish({roleId:'1',memberCount:9});await first
  assert.equal(vm.impact.value,null);assert.equal(vm.formError.value,'影响读取失败')
  await vm.submit();assert.equal(writes,0)
})

test('成员影响只属于核对过的人员，换人后必须重新核对',async()=>{
  let writes=0
  const vm=page(async()=>{writes++},async(path,params)=>path.endsWith('/impact') ? {roleId:'1',userId:params.userId} : {items:[],catalog:[],templates:[]})
  vm.members({id:'1',version:1,name:'测试角色'});vm.memberUser.value='2'
  await vm.saveMember();assert.equal(writes,0)
  await vm.refreshImpact(true);assert.equal(vm.memberImpactReady.value,true)
  vm.memberUser.value='3';await vm.saveMember();assert.equal(writes,0)
  await vm.refreshImpact(true);await vm.saveMember();assert.equal(writes,1)
})
