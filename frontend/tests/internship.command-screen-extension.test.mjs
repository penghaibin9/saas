import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { normalizeExtension, EXTENSION_VERSION } from '../src/modules/internship/components/command-screen/screen-extension.mjs'
import { readSnapshot, REQUIRED_PERMISSIONS } from '../src/modules/internship/components/command-screen/screen-core.mjs'
const sample = () => ({contractVersion:EXTENSION_VERSION,batchId:'81',snapshotAt:'2026-09-06T16:30:00+08:00',timezone:'Asia/Shanghai',totals:{students:10,enterprises:2,positions:2,schoolMentors:1,enterpriseMentors:2,pendingExceptions:3,visits7d:8,openRisks:4},regions:[{code:'440000',name:'广东省',students:8,enterprises:2}],geography:{unlocatedStudents:2,unlocatedEnterprises:0},majors:[{name:'软件技术',students:6,enterprises:2},{name:'会计',students:4,enterprises:1}],riskLevels:[{key:'HIGH',value:1},{key:'MEDIUM',value:3}],riskNewDaily:Array.from({length:7},(_,i)=>({date:`2026-09-0${i+1}`,value:i})),attendanceDaily:Array.from({length:7},(_,i)=>({date:`2026-09-0${i+1}`,value:8,compliant:7})),employmentMonths:Array.from({length:6},(_,i)=>({month:`2026-0${i+4}`,value:i})),quality:[]})
const check = data => normalizeExtension(data,10)
test('valid aggregate retains regions, eight-bound rank and meaningful zeros',()=>{const r=check(sample());assert.equal(r.available,true);assert.equal(r.totals.enterprises,2);assert.equal(r.geography.unlocatedStudents,2);assert.equal(r.issue,'')})
test('missing aggregate never becomes fabricated zero counters',()=>{const r=check(null);assert.equal(r.available,false);assert.deepEqual(r.totals,{});assert.match(r.issue,/未返回/)})
test('unknown contract version fails closed',()=>{const x=sample();x.contractVersion='unknown';assert.equal(check(x).available,false)})
test('wrong cohort size fails closed',()=>{const x=sample();x.totals.students=11;assert.equal(check(x).available,false)})
for(const key of ['students','enterprises','positions','schoolMentors','enterpriseMentors','pendingExceptions','visits7d','openRisks']){
 test(`reject missing or noninteger total ${key}`,()=>{const x=sample();delete x.totals[key];assert.equal(check(x).available,false);x.totals[key]=1.5;assert.equal(check(x).available,false)})
}
test('unidentified region records remain explicit',()=>{const x=sample();x.geography.unlocatedStudents=1;assert.equal(check(x).available,false)})
test('company region totals cannot silently omit unknown companies',()=>{const x=sample();x.geography.unlocatedEnterprises=1;assert.equal(check(x).available,false)})
test('duplicate province rows fail aggregate validation',()=>{const x=sample();x.regions=[{code:'440000',name:'广东',students:4,enterprises:1},{code:'440000',name:'广东',students:4,enterprises:1}];assert.equal(check(x).available,false)})
test('risk severity sum must equal open risk count',()=>{const x=sample();x.riskLevels[0].value=3;assert.equal(check(x).available,false)})
test('major counts cannot exceed cohort size',()=>{const x=sample();x.majors[0].students=20;assert.equal(check(x).available,false)})
test('malformed daily values become partial, never zeros',()=>{const x=sample();x.riskNewDaily[0].value=null;const r=check(x);assert.equal(r.riskNewDaily.length,6);assert.match(r.issue,/不完整/)})
test('compliant attendance cannot exceed recorded attendance',()=>{const x=sample();x.attendanceDaily[0].compliant=11;const r=check(x);assert.equal(r.attendanceDaily.length,6);assert.match(r.issue,/打卡日序列不完整/)})
test('normalized wall projection excludes unrecognized personal fields',()=>{const x=sample();x.studentName='PRIVATE';x.regions[0].latitude=23.332;x.regions[0].phone='PRIVATE';assert.equal(JSON.stringify(check(x)).includes('PRIVATE'),false);assert.equal(JSON.stringify(check(x)).includes('latitude'),false)})
test('long names are bounded rather than injected into style or HTML',()=>{const x=sample();x.majors[0].name='a'.repeat(200);assert.equal(check(x).majors[0].name.length,40)})
const ctx={batchId:'81',accessHealthy:true,grants:Object.fromEntries(REQUIRED_PERMISSIONS.map(k=>[k,true]))}
const base=()=>({batchId:'81',counters:[{key:'totalStudents',value:10}],metrics:[]})
const ok=data=>({code:0,data})
test('all four supplied loaders are batched once, no request per tile',async()=>{const calls=[];const r=await readSnapshot(Object.fromEntries(['overview','dashboard','trends','extension'].map(k=>[k,async p=>{calls.push([k,p.batchId]);return ok(k==='extension'?sample():base())}])),ctx);assert.equal(r.status,'ready');assert.equal(r.model.extra.available,true);assert.equal(calls.length,4);assert.ok(calls.every(x=>x[1]==='81'))})
test('extension HTTP 403 clears the complete result',async()=>{const r=await readSnapshot({overview:async()=>ok(base()),dashboard:async()=>ok(base()),trends:async()=>ok(base()),extension:async()=>({code:403001,message:'无权限'})},ctx);assert.equal(r.status,'denied');assert.equal(r.model,undefined)})
test('extension wrong batch is partial, never drawn on current batch',async()=>{const x=sample();x.batchId='82';const r=await readSnapshot({overview:async()=>ok(base()),dashboard:async()=>ok(base()),trends:async()=>ok(base()),extension:async()=>ok(x)},ctx);assert.equal(r.status,'ready');assert.equal(r.model.extra.available,false);assert.ok(r.model.issues.some(x=>x.includes('批次回执不一致')))})
test('production adapter cannot import preview fixtures',async()=>{const names=['screen-api.mjs','screen-core.mjs','screen-extension.mjs','screen-renderer.mjs','InternshipCommandScreen.vue'];for(const name of names){const s=await readFile(new URL('../src/modules/internship/components/command-screen/'+name,import.meta.url),'utf8');assert.doesNotMatch(s,/from\s+['"][^'"]*(?:fixture|preview)/);assert.doesNotMatch(s,/Math\.random\(/)}})
test('static visual resource has no user records or raster screenshot background',async()=>{const s=await readFile(new URL('../src/modules/internship/components/command-screen/screen-visuals.mjs',import.meta.url),'utf8');assert.doesNotMatch(s.replaceAll('http://www.w3.org/2000/svg',''),/data:image\/png|studentName|Bearer|https?:\/\//)})

test('duplicate days are not drawn as seven distinct dates',()=>{const x=sample();x.riskNewDaily[1].date=x.riskNewDaily[0].date;assert.equal(check(x).riskNewDaily.length,6);assert.match(check(x).issue,/风险新增日序列不完整/)})
test('impossible calendar dates are removed rather than silently normalized',()=>{const x=sample();x.attendanceDaily[0].date='2026-02-31';assert.equal(check(x).attendanceDaily.length,6)})
test('invalid month and duplicate month are excluded',()=>{const x=sample();x.employmentMonths[0].month='2026-13';assert.equal(check(x).employmentMonths.length,5)})
test('production three-source path needs no unused old trend request',async()=>{let calls=0;const loader=d=>async()=>{calls++;return ok(d)};const r=await readSnapshot({overview:loader(base()),dashboard:loader(base()),extension:loader(sample())},ctx);assert.equal(r.status,'ready');assert.equal(calls,3);assert.equal(r.model.extra.available,true);assert.equal(r.model.issues.length,0)})
