import test from 'node:test'
import assert from 'node:assert/strict'
import { project, formatCount } from '../src/modules/internship/components/command-screen/screen-core.mjs'

test('未接通的就业统计不能冒充零值，正常空分母与真实零值仍保留',()=>{
  const overview={metrics:[{key:'employmentRate',numerator:0,denominator:0,rate:null},{key:'weeklySubmitRate',numerator:0,denominator:0,rate:null},{key:'placementRate',numerator:0,denominator:1,rate:0}],partial:[{key:'employment',status:'NOT_CONFIGURED',message:'尚未接入'}]}
  const before=JSON.stringify(overview),model=project(overview,null,null,{batchId:'6081'})
  assert.equal(model.metrics.employmentRate.state,'unavailable')
  assert.equal(model.metrics.employmentRate.numerator,null);assert.equal(model.metrics.employmentRate.denominator,null)
  assert.equal(formatCount(model.metrics.employmentRate.numerator),'—');assert.deepEqual(model.extra.employmentMonths,[])
  assert.match(model.issues.join('；'),/就业及帮扶统计尚未接通/)
  assert.equal(model.metrics.weeklySubmitRate.state,'empty');assert.equal(model.metrics.placementRate.rate,0)
  assert.equal(JSON.stringify(overview),before)
})

test('部分不可用保留后台中文原因，已接通后的有效就业指标不被隐藏',()=>{
  const overview={metrics:[{key:'employmentRate',numerator:1,denominator:1,rate:100}],partial:[{key:'other',message:'其他统计暂不可用'}]}
  const model=project(overview,null,null,{batchId:'6081'})
  assert.equal(model.metrics.employmentRate.state,'ok');assert.equal(model.metrics.employmentRate.rate,100)
  assert.ok(model.issues.includes('其他统计暂不可用'))
})
