import test from 'node:test'
import assert from 'node:assert/strict'
import { classifyResponse, identityCounts, missingMeasuredRoutes, routeEvidence } from './lib/evidence.js'

test('HTTP success is not business success and missing/null code cannot coerce to zero',()=>{
  for(const body of [{},{code:null},{code:''},{code:403001}])assert.equal(classifyResponse({status:200,json:()=>body}).success,false)
  assert.equal(classifyResponse({status:200,json:()=>({code:0})}).success,true)
  assert.equal(classifyResponse({status:200,json:()=>{throw Error('invalid')}}).businessBucket,'invalid_json')
  assert.equal(classifyResponse({status:403}).statusBucket,'403')
  assert.equal(classifyResponse({status:0}).statusBucket,'transport')
})
test('registered zero trends and zero samples are missing routes',()=>{
  const metrics={'http_req_duration{route:r}':{values:{'p(95)':0}}}
  assert.deepEqual(missingMeasuredRoutes(routeEvidence(metrics,['r']),['r']),['r'])
  metrics['capacity_route_attempts{route:r}']={values:{count:10}}
  metrics['capacity_route_successes{route:r}']={values:{count:9}}
  assert.deepEqual(missingMeasuredRoutes(routeEvidence(metrics,['r']),['r']),[])
})
test('unique token strings are distinct from unique business subjects',()=>{
  const d=()=>({tenantId:'1',studentNo:'s',activeContextId:'ctx',capacitySynthetic:true})
  const result=identityCounts(['jwt1','jwt1','jwt2'],d,'student')
  assert.equal(result.tokens,2);assert.equal(result.identities,1);assert.equal(result.synthetic,true)
})
test('tenant+subject uniqueness does not merge two school identities',()=>{
  const result=identityCounts(['1','2'],token=>({tenantId:token,studentNo:'same'}),'student')
  assert.equal(result.identities,2)
})
test('error classifications never project raw body, token, URL or personal fields',()=>{
  const result=classifyResponse({status:200,json:()=>({code:999999,message:'private',token:'secret',phone:'13800000000'})})
  assert.deepEqual(Object.keys(result).sort(),['businessBucket','statusBucket','success'])
  assert.equal(JSON.stringify(result).includes('secret'),false)
})
