import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { formatDateTime } from '../src/utils/format.js'

test('考勤待办保留大编号并由服务端回填批次，不当作周报编号',async()=>{
  const source=fs.readFileSync(new URL('../src/services/teacherSequentialV3Api.js',import.meta.url),'utf8')
  let requested
  const api=new Function('realRequest','formatDateTime',source.replace(/^import[^\n]+\n/gm,'').replace(/export /g,'')+'\nreturn {getInternshipReviewQueue}')(
    async url=>{requested=url;return {batchId:'7',focusExceptionId:'9007199254740993',abnormalCheckins:[{id:'9007199254740993',version:2,date:'2026-10-25T04:37:00Z'}]}},formatDateTime)
  const result=await api.getInternshipReviewQueue({focusExceptionId:'9007199254740993'})
  assert.match(requested,/exceptionId=9007199254740993/)
  assert.doesNotMatch(requested,/recordId=/)
  assert.equal(result.batchId,'7');assert.equal(result.focusExceptionId,'9007199254740993')
  assert.equal(result.abnormal[0].expectedVersion,2)
  assert.equal(result.abnormal[0].time,formatDateTime('2026-10-25T04:37:00Z'))
  assert.doesNotMatch(result.abnormal[0].time,/T|Z/)
})

test('考勤异常深链进入异常页签并保留原对象供读取',()=>{
  const source=fs.readFileSync(new URL('../src/pages/teacher-internship/internship-review/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function('InternshipVisitEvidenceForm','MobileSequentialQueue','ReportFilePreview','ReportObligations','listPaging','currentSessionGeneration','toast',script)({}, {}, {}, {},()=>({}),()=>1,()=>{})
  let reads=0
  const vm={...component.data(),load(){reads++},loadVisits(){}}
  component.onLoad.call(vm,{exceptionId:'9007199254740993'})
  assert.equal(vm.tab,'abnormal');assert.equal(vm.focusExceptionId,'9007199254740993');assert.equal(vm.focusReportId,'');assert.equal(reads,1)
})

test('考勤处理调用独立后端正式接口并携带读取版本，成功后旧版本不可重用',async()=>{
  const source=fs.readFileSync(new URL('../src/services/teacherSequentialV3Api.js',import.meta.url),'utf8')
  const writes=[]
  const api=new Function('realRequest','formatDateTime',source.replace(/^import[^\n]+\n/gm,'').replace(/export /g,'')+'\nreturn {getInternshipReviewQueue,handleCheckin}')(
    async(url,options)=>{if(options){writes.push({url,options});return {id:'9007199254740993',status:'COMPLETED'}}return {abnormalCheckins:[{id:'9007199254740993',version:2}]}},formatDateTime)
  await api.getInternshipReviewQueue()
  await api.handleCheckin('9007199254740993','REASONABLE','已核对本次测试证据')
  assert.equal(writes[0].url,'/internship/exceptions/9007199254740993/handle')
  assert.equal(writes[0].options.data.expectedVersion,2)
  await assert.rejects(()=>api.handleCheckin('9007199254740993','REASONABLE','重复提交'),/版本已失效/)
  assert.equal(writes.length,1)
})
