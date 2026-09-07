import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildViewModel,emptyView,domain,num,count,routeTarget,safeAsset,identityKey,ENDPOINTS} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-data.mjs';
import {setImmediate} from 'node:timers';
import {createConnector} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-connector.mjs';
import {routeAllowed,createWallRuntime,refreshInterval} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-runtime.mjs';
import {escapeHtml,validateBrandPatch} from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-view.mjs';
import {makeFixture} from './fixtures/leadership-wall.mjs';
const metric=(d,k)=>buildViewModel(d).metrics[k];
const can=(ctx,k)=>ctx.permissionPatterns?.includes('*')||ctx.permissionPatterns?.includes(k);
const ctx={permissionPatterns:['*'],dataScope:{scopeName:'测试范围'}};
function rig({override={},permission=ctx,identity=()=> 'tenant-1/admin',requestHook}={}){
 const d=makeFixture(),calls=[];
 const data={context:permission,brand:{schoolName:'测试学校'},term:d.term.data,reminders:d.reminders.data,readiness:d.readiness.data,quality:d.quality.data,...override};
 const request=async(path,options)=>{calls.push({path,options});if(requestHook)return requestHook(path,options,data);const k=Object.keys(ENDPOINTS).find(k=>ENDPOINTS[k].path===path);const v=data[k];if(v instanceof Error)throw v;return structuredClone(v);};
 let invalidations=0;
 return {c:createConnector({request,can,identity,onInvalidate:()=>invalidations++}),calls,data,invalidations:()=>invalidations};
}
const wait=()=>new Promise(r=>setImmediate(r));

test('fixture: audited counts/ratios and all 34 metrics are usable',()=>{const v=buildViewModel(makeFixture());assert.equal(v.state,'READY');assert.equal(Object.keys(v.metrics).length,34);assert.equal(v.metrics.todayTotal.value,1268);assert.equal(v.metrics.gradeSubmitted.value,1262);assert.equal(v.metrics.roomRate.value,87.3);});
for(const v of [null,undefined,'0','23',NaN,Infinity,-1,1.5,Number.MAX_SAFE_INTEGER+1])test(`invalid count rejected: ${String(v)}`,()=>assert.equal(count(v),null));
test('zero is a valid number, not a missing value',()=>{assert.equal(count(0),0);assert.equal(num(0),0);});
test('missing metric never falls back to sample or zero',()=>{const d=makeFixture();delete d.reminders.data.todayTeaching.teacherCount;assert.equal(metric(d,'teacherCount').value,null);});
test('scopeRestricted removes all school totals and the quality leak path',()=>{const d=makeFixture();d.reminders.data.scopeRestricted=true;const v=buildViewModel(d);assert.equal(v.state,'RESTRICTED');assert.equal(v.metrics.todayTotal.value,null);assert.equal(v.metrics.taskRate.value,null);assert.deepEqual(v.courses,[]);});
test('missing scope flag fails closed',()=>{const d=makeFixture();delete d.reminders.data.scopeRestricted;assert.equal(metric(d,'todayTotal').value,null);});
test('unknown teaching timing uses the exact remainder only',()=>{const d=makeFixture();d.reminders.data.todayTeaching.ended=100;assert.equal(metric(d,'unknownSlots').value,12);});
test('impossible teaching partition invalidates totals',()=>{const d=makeFixture();d.reminders.data.todayTeaching.inProgress=99999;assert.equal(metric(d,'todayTotal').state,'INVALID');});
test('sparse grade status dictionary zeroes absent states only after reconciliation',()=>{const d=makeFixture();assert.equal(metric(d,'gradeArchived').value,0);d.reminders.data.gradeProgress.counts={};assert.equal(metric(d,'gradeArchived').value,null);});
test('archived grades never silently join submitted numerator',()=>{const d=makeFixture(),g=d.reminders.data.gradeProgress;g.counts.PUBLISHED-=10;g.counts.ARCHIVED=10;g.submittedRate=97.8;assert.equal(metric(d,'gradeSubmitted').value,1252);});
test('all-zero grade total has undefined percent, not 0%',()=>{const d=makeFixture();d.reminders.data.gradeProgress={totalTasks:0,counts:{},submittedRate:0};assert.equal(metric(d,'gradeTotal').value,0);assert.equal(metric(d,'gradeSubmittedRate').state,'NO_DATA');});
test('unknown grade enum kept as other, not omitted from ring',()=>{const d=makeFixture();d.reminders.data.gradeProgress.counts.RETURNED=0;d.reminders.data.gradeProgress.counts.NEW_ENUM=2;assert.equal(buildViewModel(d).gradeSegments.reduce((s,r)=>s+r.value,0),1280);});
test('grade rate must reconcile with statuses',()=>{const d=makeFixture();d.reminders.data.gradeProgress.submittedRate=12;assert.equal(metric(d,'gradeSubmittedRate').state,'INVALID');});
test('no room dictionary means no occupancy percentage',()=>{const d=makeFixture();d.reminders.data.resourceOccupancy={totalRooms:0,occupiedToday:0,occupancyRate:0};assert.equal(metric(d,'roomRate').state,'NO_DATA');});
test('room occupancy above capacity is hidden',()=>{const d=makeFixture();d.reminders.data.resourceOccupancy.occupiedToday=999;assert.equal(metric(d,'occupiedRooms').value,null);});
test('public/legacy term mismatch removes all today details, not cumulative grades',()=>{const d=makeFixture();d.term.data.yearCode='2025-2026';const v=buildViewModel(d);assert.equal(v.metrics.todayTotal.value,null);assert.equal(v.courses.length,0);assert.equal(v.resources.length,0);assert.equal(v.metrics.gradeTotal.value,1280);});
test('readiness term mismatch never combines terms',()=>{const d=makeFixture();d.readiness.data.term.termId='999';assert.equal(metric(d,'blockers').state,'INVALID');assert.deepEqual(buildViewModel(d).issues,[]);});
test('duplicate quality keys are not picked arbitrarily',()=>{const d=makeFixture();d.quality.data.indicators.push({...d.quality.data.indicators[0]});assert.equal(metric(d,'failRate').state,'INVALID');});
test('quality denominator zero is not a 0% claim',()=>{const d=makeFixture();Object.assign(d.quality.data.indicators[0],{value:0,numerator:0,denominator:0});assert.equal(metric(d,'failRate').state,'NO_DATA');});
test('quality percentages must agree with numerator and denominator',()=>{const d=makeFixture();d.quality.data.indicators[0].value=99;assert.equal(metric(d,'failRate').state,'INVALID');});
test('malformed optional arrays do not crash adapter',()=>{const d=makeFixture();d.quality.data.indicators.push(null);d.reminders.data.dataTrends.series.push(null);assert.doesNotThrow(()=>buildViewModel(d));assert.doesNotThrow(()=>buildViewModel(null));});
test('preview rows bounded; totals are not recomputed from page lengths',()=>{const d=makeFixture();const v=buildViewModel(d);assert.equal(v.courses.length,30);assert.equal(v.resources.length,10);assert.equal(v.metadata.courseCount,1268);});
test('warning names, reasons and teacher names are excluded from output',()=>{const text=JSON.stringify(buildViewModel(makeFixture()));for(const k of ['敏感样本不可显示','不应投屏的个人情况','此字段不会传入展示模型'])assert.ok(!text.includes(k));});
test('null trend points suppress that series rather than interpolating',()=>{const d=makeFixture();d.reminders.data.dataTrends.series[0].points[0].value=null;assert.ok(!buildViewModel(d).trends.some(x=>x.key==='gradeSubmit'));});
test('an optional failed endpoint is shown as partial, not all-ready',()=>{const d=makeFixture();d.quality=domain('ERROR');assert.equal(buildViewModel(d).state,'PARTIAL');});
test('empty states contain no fixture data',()=>{assert.equal(emptyView().metrics.todayTotal.value,null);assert.equal(emptyView('ERROR').courses.length,0);});
for(const path of ['https://bad.test/','//bad.test/','javascript:alert(1)','/admin/academic-affairs/../system','/admin/academic-affairs/%2e%2e/system','/admin/academic-affairs/%2fsystem','aa-test x'])test(`route blocks ${path}`,()=>assert.equal(routeTarget(path),null));
test('known routes and on-module query deep links preserved',()=>{assert.deepEqual(routeTarget('aa-schedule'),{name:'aa-schedule'});assert.deepEqual(routeTarget('/admin/academic-affairs/warnings?state=open'),{path:'/admin/academic-affairs/warnings?state=open'});});
test('asset URL rejects executable and protocol-relative schemes',()=>{assert.equal(safeAsset('javascript:alert(1)'),'');assert.equal(safeAsset('//bad.test/a.svg'),'');assert.equal(safeAsset('/assets/a.webp'),'/assets/a.webp');});
test('HTML labels are escaped',()=>assert.equal(escapeHtml('<img src=x onerror="x">'),'&lt;img src=x onerror=&quot;x&quot;&gt;'));
test('brand schema rejects bad colors, lengths and timers',()=>{for(const b of [{primary:'red;display:none'},{title:'a'.repeat(200)},{refreshSeconds:1},{timezone:'INVALID'},{mapMotto:'bad'},{unknown:1}])assert.throws(()=>validateBrandPatch(b));});
test('identity includes tenant, user, role and active context',()=>assert.notEqual(identityKey({tenantId:1,userId:1,currentRoleCode:'AA',activeContextId:'a'}),identityKey({tenantId:2,userId:1,currentRoleCode:'AA',activeContextId:'a'})));

test('connector uses audited GET endpoints and only readiness receives termId',async()=>{const r=rig();const out=await r.c.load();assert.equal(out.state,'READY');const calls=r.calls;assert.equal(calls.length,6);assert.deepEqual(calls.find(x=>x.path===ENDPOINTS.readiness.path).options.params,{termId:'202601'});for(const k of ['quality','reminders'])assert.equal(calls.find(x=>x.path===ENDPOINTS[k].path).options.params,undefined);});
test('dashboard permission missing prevents any business call',async()=>{const r=rig({permission:{permissionPatterns:[]}});assert.equal((await r.c.load()).state,'RESTRICTED');assert.equal(r.calls.length,1);});
test('rbacOk false fails closed',async()=>{const r=rig({permission:{permissionPatterns:['*'],rbacOk:false}});assert.equal((await r.c.load()).state,'RESTRICTED');});
test('no term never queries mixed-term summaries',async()=>{const r=rig({override:{term:{termId:''}}});const x=await r.c.load();assert.equal(x.metrics.todayTotal.value,null);assert.ok(!r.calls.some(x=>x.path===ENDPOINTS.reminders.path));});
test('narrow scope never requests school quality',async()=>{const d=makeFixture();d.reminders.data.scopeRestricted=true;const r=rig({override:{reminders:d.reminders.data}});assert.equal((await r.c.load()).state,'RESTRICTED');assert.ok(!r.calls.some(x=>x.path===ENDPOINTS.quality.path));});
test('quality failure preserves independent reminders',async()=>{const r=rig({override:{quality:new Error('db error')}});const x=await r.c.load();assert.equal(x.state,'PARTIAL');assert.equal(x.metrics.todayTotal.value,1268);assert.equal(x.metrics.taskRate.value,null);});
test('identity change drops stale successful responses',async()=>{let id='A';const r=rig({identity:()=>id,requestHook:async(p,o,d)=>{const k=Object.keys(ENDPOINTS).find(k=>ENDPOINTS[k].path===p);if(k==='reminders')id='B';return d[k];}});assert.equal(await r.c.load(),null);});
test('latest load wins even if prior load finishes later',async()=>{let release,n=0;const r=rig({requestHook:async(p,o,d)=>{const k=Object.keys(ENDPOINTS).find(k=>ENDPOINTS[k].path===p);if(k==='context'&&++n===1)await new Promise(r=>release=r);return d[k];}});const first=r.c.load();await wait();const second=await r.c.load();release();assert.equal(await first,null);assert.equal(second.state,'READY');});
test('authentication failure clears previous data via onInvalidate',async()=>{const error=Object.assign(new Error('expired'),{code:401001});const r=rig({override:{quality:error}});assert.equal(await r.c.load(),null);assert.equal(r.invalidations(),1);});
test('authorize always rechecks fresh context',async()=>{const r=rig();await r.c.load();r.data.context={permissionPatterns:[]};assert.equal(await r.c.authorize('teaching'),null);});
test('dispose prevents publication and navigation',async()=>{const r=rig();await r.c.load();r.c.dispose();assert.equal(await r.c.load(),null);assert.equal(await r.c.authorize('teaching'),null);});
test('route permissionKey, permissionAny and permissionAll checked',()=>{const c={permissionPatterns:['a','b']};assert.ok(routeAllowed({matched:[{meta:{permissionKey:'a',permissionAny:['c','b'],permissionAll:['a','b']}}]},c,can));assert.ok(!routeAllowed({matched:[{meta:{permissionAny:['c']}}]},c,can));assert.ok(!routeAllowed({matched:[]},c,can));});
test('refresh interval clamped to safe range',()=>{assert.equal(refreshInterval(1),30000);assert.equal(refreshInterval(9999),600000);assert.equal(refreshInterval(NaN),60000);});
test('runtime coalesces requests, clears old identity, disposes timers',async()=>{
 let release,id='A',loads=0,reset=0,disposed=0,destroy=0,clear=0;const updates=[];
 const runtime=createWallRuntime({identity:()=>id,connector:{load:async()=>{loads++;if(loads===1)await new Promise(r=>release=r);return {loads};},invalidate(){},dispose(){disposed++;}},view:{update:x=>updates.push(x),reset(){reset++;},destroy(){destroy++;}},setTimer:()=>1,clearTimer:()=>clear++});
 runtime.start();await wait();runtime.refresh();id='B';runtime.checkIdentity();release();await wait();await wait();assert.equal(reset,1);assert.equal(loads,2);assert.equal(updates.length,1);runtime.dispose();assert.equal(disposed,1);assert.equal(destroy,1);assert.equal(clear,2);
});
test('production source has no fixture import or token persistence',()=>{for(const p of ['AaLeadershipWallView.vue','aa-wall-connector.mjs','aa-wall-runtime.mjs']){const t=fs.readFileSync(new URL('../src/modules/academicAffairs/components/leadershipWall/'+(p.endsWith('.vue')?'../../views/'+p:p),import.meta.url),'utf8');assert.ok(!/fixture|VISUAL_SPATIAL|localStorage|sessionStorage/.test(t));}});

// Narrow compatibility mapping verified against the actual frontend route tree.
test('readiness schedule-change route maps to canonical existing page',()=>assert.deepEqual(routeTarget('/admin/academic-affairs/schedule-changes'),{path:'/admin/academic-affairs/schedule-change'}));
test('canonical route mapping preserves filters and anchor',()=>assert.deepEqual(routeTarget('/admin/academic-affairs/schedule-changes?status=SUBMITTED#queue'),{path:'/admin/academic-affairs/schedule-change?status=SUBMITTED#queue'}));
test('route mapping does not rewrite unverified longer paths',()=>assert.deepEqual(routeTarget('/admin/academic-affairs/schedule-changes/example'),{path:'/admin/academic-affairs/schedule-changes/example'}));
