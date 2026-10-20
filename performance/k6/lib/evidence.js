/** Pure, bounded, redacted evidence. Shared by k6 and Node behavior tests. */
export const STATUS_BUCKETS = ['transport', '200', 'other2xx', '3xx', '400', '401', '403', '404', '409', '422', '429', 'other4xx', '5xx', 'other']
export const BUSINESS_BUCKETS = ['ok', 'http', 'invalid_json', 'missing_code', 'unauthorized', 'forbidden', 'conflict', 'validation', 'other']
export function classifyResponse(response) {
  const status=Number(response?.status || 0)
  let statusBucket=String(status)
  if (!STATUS_BUCKETS.includes(statusBucket)) statusBucket=status===0?'transport':status<200?'other':status<300?'other2xx':status<400?'3xx':status<500?'other4xx':'5xx'
  if(status!==200)return {statusBucket,businessBucket:'http',success:false}
  let body
  try{body=response.json()}catch{return {statusBucket,businessBucket:'invalid_json',success:false}}
  if(!body||typeof body!=='object'||!Object.prototype.hasOwnProperty.call(body,'code')||body.code===null||body.code==='')return {statusBucket,businessBucket:'missing_code',success:false}
  if(Number(body.code)===0)return {statusBucket,businessBucket:'ok',success:true}
  const code=Number(body.code)
  const businessBucket=code===401001?'unauthorized':code===403001?'forbidden':code===409001?'conflict':[400001,422001].includes(code)?'validation':'other'
  return {statusBucket,businessBucket,success:false}
}
function count(metrics,name){const n=Number(metrics[name]?.values?.count);return Number.isSafeInteger(n)&&n>=0?n:0}
export function routeEvidence(metrics,routes) {
  const result={}
  for(const route of routes){
    const attempts=count(metrics,`capacity_route_attempts{route:${route}}`)
    const successes=count(metrics,`capacity_route_successes{route:${route}}`)
    result[route]={attempts,successes,failures:Math.max(0,attempts-successes),statuses:{},business:{}}
    for(const bucket of STATUS_BUCKETS)result[route].statuses[bucket]=count(metrics,`capacity_http_${bucket}{route:${route}}`)
    for(const bucket of BUSINESS_BUCKETS)result[route].business[bucket]=count(metrics,`capacity_business_${bucket}{route:${route}}`)
  }
  return result
}
export function missingMeasuredRoutes(evidence,required){
  return required.filter(route=>!evidence[route]||evidence[route].attempts<=0||evidence[route].successes<=0)
}
export function identityCounts(tokens,decode,role) {
  const identities=new Set(),contexts=new Set(),uniqueTokens=new Set()
  let synthetic=false,invalid=0
  for(const token of tokens){
    if(typeof token!=='string'||!token){invalid+=1;continue}
    uniqueTokens.add(token)
    const claims=decode(token)||{}
    const tenant=String(claims.tenantId||'')
    const subject=String(role==='student'?(claims.studentId||claims.studentNo||''):(claims.userId||''))
    if(!tenant||!subject){invalid+=1;continue}
    identities.add(JSON.stringify([tenant,subject]))
    if(claims.activeContextId)contexts.add(JSON.stringify([tenant,String(claims.activeContextId)]))
    if(claims.capacitySynthetic===true||claims.tid==='perf-local'||String(claims.loginName||'').startsWith('PERF-'))synthetic=true
  }
  return {tokens:uniqueTokens.size,identities:identities.size,contexts:contexts.size,synthetic,invalid}
}
