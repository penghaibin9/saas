import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
const read = p => readFileSync(new URL(p, import.meta.url), 'utf8')
test('总览聚合有独立30秒等待时间且保留原筛选', async () => {
 const source=read('../src/modules/academicAffairs/api/academic-affairs.api.js')
 const method=source.match(/getStatsOverview\(params = \{\}\) \{([\s\S]*?)\n  \},/)[1]
 let captured
 const run=vm.runInNewContext('(async (params) => {'+method+'})', {BASE:'/academic-affairs',call:fn=>fn(),request:(path,options)=>{captured={path,...options};return {value:1}}})
 const params={termId:'51',collegeId:'120'}
 await run(params)
 assert.equal(captured.timeoutMs,30000)
 assert.equal(captured.params,params)
 assert.equal(captured.path,'/academic-affairs/stats/overview')
})
test('空明细和读取失败的返回按钮收起当前明细，不离开统计范围', () => {
 const source=read('../src/modules/academicAffairs/views/AaStatsOverviewView.vue')
 for(const name of ['drill','detail']) {
  for(const tag of ['EmptyState','ErrorState']) {
   const element=source.match(new RegExp('<'+tag+'[^>]*'+name+'\\.(?:rows|error)[^>]*>'))?.[0]
   assert.ok(element, tag+' '+name)
   assert.match(element,new RegExp('@back="'+(name==='drill'?'closeDrill':'closeDetail')+'"'))
  }
 }
})

import { statsGroupLabel } from '../src/modules/academicAffairs/views/parallel-c/stats-presentation.js'
test('学籍统计的注册、毕业与原现状态使用中文', () => {
 assert.equal(statsGroupLabel({key:'ENROLL_REGISTER'}),'入学注册')
 assert.equal(statsGroupLabel({key:'GRADUATE'}),'毕业')
 assert.equal(statsGroupLabel({key:'NORMAL'}),'正常在籍')
 const source=read('../src/modules/academicAffairs/views/AaStatsOverviewView.vue')
 for(const field of ['changeType','fromStatus','toStatus']) {
  assert.ok(source.split('#cell-'+field+'=').length>=3,field+' must cover both detail tables')
 }
 assert.equal(statsGroupLabel({key:'INTERNAL_UNKNOWN'}),'未分类')
})

test('课表单双周使用中文且详情有对应插槽', () => {
 assert.equal(statsGroupLabel({key:'ALL'}),'全周')
 assert.equal(statsGroupLabel({key:'ODD'}),'单周')
 assert.match(read('../src/modules/academicAffairs/views/AaStatsOverviewView.vue'),/#cell-weekParity=/)
})

test('成绩等聚合统计同样使用30秒等待，不修改普通明细请求', () => {
 const source=read('../src/modules/academicAffairs/api/academic-affairs.api.js')
 for(const name of ['getStatsGrade','getStatsWorkload','getStatsRegistrationSummary','getStatsWarningSummary']) {
  const method=source.match(new RegExp(name+'\\(params = \\{\\}\\) \\{([\\s\\S]*?)\\},'))[1]
  assert.match(method,/timeoutMs: 30000/)
 }
 assert.match(source,/getStatsGradeDetail[^\n]*callList/)
})

import { academicStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'
test('毕业批次选择器不显示内部状态码', () => {
 const source=read('../src/modules/academicAffairs/pickerAdapters.js').replace(/\r\n/g, '\n')
 const expression=source.match(/const graduationBatch = ([\s\S]*?)\n\nconst registrationBatch/)[1]
 const config=vm.runInNewContext(expression,{searchable:(_fetch,config)=>config,academicAffairsApi:{},academicStatusLabel})
 assert.equal(config.desc({status:'ARCHIVED'}),'已归档')
 assert.equal(config.desc({status:'PRECHECKED'}),'已预审')
 assert.equal(config.desc({status:'NEW_UNKNOWN'}),'状态待确认')
})

test('快照空列表返回清空筛选，详情错误返回关闭详情', () => {
 const source=read('../src/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue')
 assert.match(source,/<EmptyState[^>]*@back="resetSearch"/)
 assert.match(source,/<ErrorState[^>]*detailError[^>]*@back="closeDetail"/)
})
