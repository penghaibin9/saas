import test from 'node:test';
import assert from 'node:assert/strict';
import {buildViewModel,domain,previewState,ENDPOINTS} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-data.mjs';
import {createConnector} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-connector.mjs';
import {previewMessage,wallStatus,metricDescription,sourceTimeLabel} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-presentation.mjs';
import {makeFixture} from './fixtures/leadership-wall.mjs';

function emptySchool(){
  const d=makeFixture(),r=d.reminders.data;
  Object.assign(r.todayTeaching,{totalToday:0,notStarted:0,inProgress:0,ended:0,teacherCount:0,classCount:0,roomCount:0,adjustedCount:0,examCount:0});
  r.todayCourses={count:0,shown:0,items:[]};
  r.resourceOccupancy={totalRooms:0,occupiedToday:0,occupancyRate:0,unmatchedCount:0,items:[]};
  r.examReminders={count:0,windowDays:14,items:[]};
  r.gradeProgress={totalTasks:0,counts:{},submittedRate:0};
  return d;
}
test('successful empty school has no false unavailable warning and no made-up percentage',()=>{
  const v=buildViewModel(emptySchool());
  assert.equal(v.state,'READY');
  assert.equal(v.metrics.gradeSubmittedRate.value,null);
  assert.equal(v.metrics.roomRate.value,null);
  assert.equal(wallStatus(v),'统计已更新 · 部分暂无数据');
  assert.match(previewMessage('courses',v.metadata,v.metrics)[0],/今日暂无/);
  assert.match(previewMessage('exams',v.metadata,v.metrics)[1],/14天/);
  assert.equal(previewMessage('resources',v.metadata,v.metrics)[0],'教室资料待配置');
});
test('configured rooms with no use have a different empty state from unconfigured rooms',()=>{
  const d=emptySchool();d.reminders.data.resourceOccupancy.totalRooms=5;
  const v=buildViewModel(d);
  assert.equal(v.metrics.roomRate.value,0);
  assert.equal(previewMessage('resources',v.metadata,v.metrics)[0],'今日暂无教室使用记录');
});
for(const state of ['ERROR','RESTRICTED','MISSING','INVALID'])test(`${state} is never called no courses or no exams`,()=>{
  const d=emptySchool();d.reminders=domain(state);
  const v=buildViewModel(d);
  assert.notEqual(v.state,'READY');
  assert.notEqual(v.metadata.previews.courses,'NO_DATA');
  assert.doesNotMatch(previewMessage('courses',v.metadata,v.metrics)[0],/今日暂无/);
});
test('missing or inconsistent list cannot be mistaken for an empty list',()=>{
  assert.equal(previewState('OK',undefined,0),'MISSING');
  assert.equal(previewState('OK',[],4),'MISSING');
  assert.equal(previewState('OK',[{}],0),'INVALID');
  assert.equal(previewState('OK',[],0,true),'INVALID');
});
test('quality invalid ratio still flags partial even with a valid empty school',()=>{
  const d=emptySchool();d.quality.data.indicators[0].value=99;
  assert.equal(buildViewModel(d).state,'PARTIAL');
});
test('refresh replaces empty results with server rows and full totals when data becomes available',async()=>{
  let d=emptySchool();
  const c=createConnector({identity:()=> 'test-school-admin',can:()=>true,request:async path=>{
    const key=Object.keys(ENDPOINTS).find(k=>ENDPOINTS[k].path===path);
    if(key==='context')return {rbacOk:true,permissionPatterns:['academicAffairs.dashboard.view']};
    if(key==='brand')return {schoolName:'测试学校'};
    return structuredClone(d[key].data);
  }});
  const before=await c.load();assert.equal(before.courses.length,0);
  d=makeFixture();
  const after=await c.load();
  assert.equal(after.metadata.previews.courses,'OK');
  assert.equal(after.courses.length,30);
  assert.equal(after.metrics.todayTotal.value,1268);
  assert.equal(after.metadata.courseCount,1268);
  assert.equal(after.resources.length,10);
  assert.equal(after.exams.length,5);
  assert.equal(after.metrics.examUpcoming.value,18);
  c.dispose();
});
test('business explanation is readable while calculation is unchanged',()=>{
  const v=buildViewModel(emptySchool());
  const text=metricDescription(v.metrics.gradeSubmittedRate);
  assert.match(text,/已提交/);assert.match(text,/全部成绩任务/);
  assert.doesNotMatch(text,/SUBMITTED|totalTasks/);
});
test('timestamp displays the school timezone with and without explicit UTC marker',()=>{
  assert.equal(sourceTimeLabel('2026-09-07T03:12:00'),sourceTimeLabel('2026-09-07T03:12:00Z'));
  assert.match(sourceTimeLabel('2026-09-07T03:12:00Z'),/11:12/);
  assert.equal(sourceTimeLabel('invalid'),'更新时间待核对');
});
