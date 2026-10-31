import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/modules/internship/api/score.api.js',import.meta.url),'utf8')
function api(request){const script=source.replace(/^import[^\n]+\r?\n/gm,'').replace('export const scoreApi','const scoreApi').replace(/export default scoreApi;?/,'')+'\nreturn scoreApi';return new Function('request','getToken','API_BASE_URL','API_PREFIX',script)(request,()=>'', '', '/api/v1')}
test('成绩写冲突透传业务原因，页面可保留原版本与意见',async()=>{
  const client=api(async()=>{throw {biz:true,code:400001,httpStatus:400,bizCode:'DATA_CONFLICT',message:'来源已变化'}})
  for(const promise of [client.compute({internshipId:'1',expectedVersion:0}),client.review('1',{expectedVersion:0}),client.publish('1',{expectedVersion:0})]){const r=await promise;assert.equal(r.bizCode,'DATA_CONFLICT');assert.equal(r.message,'来源已变化');assert.equal(r.code,400001)}
})
