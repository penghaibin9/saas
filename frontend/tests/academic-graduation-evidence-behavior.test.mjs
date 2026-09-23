import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as graduation from '../src/modules/academicAffairs/constants/grade-graduation.js'
import { academicStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'

function instance() {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const bindings=[...source.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm)].flatMap(([,binding])=>binding.trim().startsWith('{')?binding.replace(/[{}]/g,'').split(',').map(s=>s.trim()).filter(Boolean):[binding.trim()])
  const deps={...graduation,academicStatusLabel,currentUserFromToken:()=>({})}
  const component=new Function(...bindings,source.replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"]\s*$/gm,'').replace('export default','return'))(...bindings.map(key=>deps[key]??{}))
  const vm={...component.data(),$route:{query:{tab:'results'}},ctx:{}}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.batchId='12';vm.batches=[{batchId:'12',batchName:'验收批次',status:'PRECHECKED',total:2,passed:0,abnormal:2,concluded:0,archived:0}]
  return vm
}

test('浏览结果或归档页不会把未完成的学院审核和终审打勾',()=>{
  const vm=instance()
  assert.equal(vm.stageIndex,2)
  vm.$route.query.tab='archive';assert.equal(vm.stageIndex,2)
  vm.batches[0].abnormal=0;vm.batches[0].passed=2
  assert.equal(vm.stageIndex,3)
  vm.batches[0].concluded=2;assert.equal(vm.stageIndex,5)
  vm.batches[0].status='ARCHIVED';assert.equal(vm.stageIndex,6)
})

test('毕业名单展示正式学号而不是学生内部编号',()=>{
  const vm=instance()
  const columns=Object.values(vm).filter(Array.isArray).flat().filter(item=>item?.title==='学号')
  assert.ok(columns.length>=4)
  assert.ok(columns.every(item=>item.key==='studentNo'))
})

test('毕业批次和学籍证据使用中文业务说明',()=>{
  const vm=instance()
  assert.equal(vm.batchOptions[0].label,'验收批次（已预审，应审 2）')
  assert.equal(vm.evidenceText('student_status=NORMAL'),'学籍状态：正常在籍')
  assert.equal(vm.evidenceText('已得 6.0/2.0 学分'),'已得 6.0/2.0 学分')
})
