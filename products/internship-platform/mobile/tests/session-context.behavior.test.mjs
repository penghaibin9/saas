import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import { request, normalizeError } from './request-module.mjs'

test('统一响应的业务冲突保留安全中文原因，重复催交不冒充服务故障', async () => {
  const storage = new Map()
  let message = '5分钟内已催交，请稍后再试', bizCode = 'DATA_CONFLICT'
  globalThis.uni = { getStorageSync: key => storage.get(key), setStorageSync: (key, value) => storage.set(key, value), removeStorageSync: key => storage.delete(key),
    request: options => options.success({ statusCode: 400, data: { code: 1, bizCode, message } }) }
  try {
    const rejected = async () => {
      try { await request.realRequest('/internship/report-obligations/1/remind', { method: 'POST', auth: false }); assert.fail('应当拒绝重复催交') }
      catch (error) { return error }
    }
    assert.equal(normalizeError(await rejected()).text, message)
    message = 'DATA_CONFLICT: SQLAlchemy Exception secret'; assert.doesNotMatch(normalizeError(await rejected()).text, /SQL|secret|DATA_CONFLICT/)
    bizCode = 'DATA_NOT_FOUND'; message = '学生没有有效绑定账号，未发送提醒'
    assert.deepEqual(normalizeError(await rejected()), { kind: 'notfound', text: message })
    bizCode = 'UNKNOWN_REASON'; message = '未经识别的内部原因'; assert.equal(normalizeError(await rejected()).text, '操作失败，请稍后重试')
  } finally { delete globalThis.uni }
})

test('实际401响应只刷新一次，普通请求和附件重试均沿用当前会话', async () => {
  const storage=new Map(),calls=[]
  globalThis.uni={getStorageSync:key=>storage.get(key),setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),
    request:options=>{
      calls.push(options)
      if(options.url.endsWith('/auth/refresh')) options.success({statusCode:200,data:{code:0,data:{accessToken:'new-access',refreshToken:'new-refresh'}}})
      else options.success(options.header.Authorization==='Bearer new-access'
        ?{statusCode:200,data:{code:0,data:{id:'kept-object'}}}
        :{statusCode:401,data:{code:1,bizCode:'UNAUTHORIZED'}})
    },
    uploadFile:options=>{
      calls.push(options)
      options.success(options.header.Authorization==='Bearer new-access'
        ?{statusCode:200,data:JSON.stringify({code:0,data:{id:'kept-file'}})}
        :{statusCode:401,data:JSON.stringify({code:1,bizCode:'UNAUTHORIZED'})})
    }}
  try {
    for(const upload of [false,true]) {
      calls.length=0;request.commitNewSessionTokens('old-access','old-refresh')
      const result=upload?await request.realUpload('/files/upload','local-file.xlsx'):await request.realRequest('/mobile/me')
      assert.equal(result.id,upload?'kept-file':'kept-object')
      assert.equal(calls.filter(x=>x.url.endsWith('/auth/refresh')).length,1)
      assert.equal(calls.length,3)
      assert.equal(calls.at(-1).header.Authorization,'Bearer new-access')
    }
  } finally {request.clearTokens();delete globalThis.uni}
})

test('移动身份切换在自动续期后使用新凭据，普通业务请求内容保持不变', async () => {
  const storage=new Map(),calls=[]
  globalThis.uni={getStorageSync:key=>storage.get(key),setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),
    request:options=>{
      calls.push(options)
      if(options.url.endsWith('/auth/refresh')) options.success({statusCode:200,data:{code:0,data:{accessToken:'renewed-access',refreshToken:'renewed-refresh'}}})
      else if(options.header.Authorization==='Bearer renewed-access' && (!options.url.endsWith('/auth/switch-role') || options.data.refreshToken==='renewed-refresh'))
        options.success({statusCode:200,data:{code:0,data:{roleCode:'COLLEGE_ADMIN'}}})
      else options.success({statusCode:401,data:{code:401001,bizCode:'UNAUTHORIZED'}})
    }}
  try {
    for(const access of ['expired-access','']) {
      calls.length=0;request.commitNewSessionTokens(access,'old-refresh')
      const payload={roleCode:'COLLEGE_ADMIN',refreshToken:'old-refresh'}
      assert.equal((await request.realRequest('/auth/switch-role',{method:'POST',data:payload})).roleCode,'COLLEGE_ADMIN')
      assert.equal(calls.filter(x=>x.url.endsWith('/auth/refresh')).length,1)
      assert.equal(calls.at(-1).data.refreshToken,'renewed-refresh')
      assert.equal(calls.at(-1).data.roleCode,'COLLEGE_ADMIN')
      assert.equal(payload.refreshToken,'old-refresh','不修改调用方保存的原始提交内容')
    }
    request.commitNewSessionTokens('expired-access','old-refresh')
    await request.realRequest('/mobile/ordinary-command',{method:'POST',data:{refreshToken:'business-field'}})
    assert.equal(calls.at(-1).data.refreshToken,'business-field')
  } finally {request.clearTokens();delete globalThis.uni}
})

test('旧身份切换收到续期拒绝时不能借用新账号凭据重试', async () => {
  const storage=new Map(),calls=[]
  globalThis.uni={getStorageSync:key=>storage.get(key),setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),
    request:options=>{calls.push(options)}}
  try {
    request.commitNewSessionTokens('old-access','old-refresh')
    const changing=request.realRequest('/auth/switch-role',{method:'POST',data:{roleCode:'COLLEGE_ADMIN',refreshToken:'old-refresh'}})
    request.commitNewSessionTokens('different-account-access','different-account-refresh')
    calls[0].success({statusCode:401,data:{code:401001,bizCode:'UNAUTHORIZED'}})
    await assert.rejects(changing,error=>error.staleSession===true)
    assert.equal(calls.length,1)
    assert.equal(request.getToken(),'different-account-access')
    assert.equal(request.getRefreshToken(),'different-account-refresh')
  } finally {request.clearTokens();delete globalThis.uni}
})

test('移动退出携带退出前访问凭据，不为退出刷新令牌，并清除本地身份', async () => {
  const storage=new Map(),calls=[]
  globalThis.uni={getStorageSync:key=>storage.get(key),setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),
    request:options=>{calls.push(options);options.success({statusCode:401,data:{code:1,bizCode:'UNAUTHORIZED'}})}}
  const source=fs.readFileSync(new URL('../src/services/mobileAuth.js',import.meta.url),'utf8')
    .replace(/^import[^\n]+\n/gm,'').replace(/export /g,'')
  const {currentSessionGeneration}=await import('../src/services/sessionGeneration.mjs')
  const names=['clearTokens','commitNewSessionTokens','getToken','getRefreshToken','realRequest']
  const logout=new Function(...names,'setForcePasswordChange','currentSessionGeneration',source+'\nreturn logoutMobile')(...names.map(name=>request[name]),()=>{},currentSessionGeneration)
  try {
    request.commitNewSessionTokens('logout-access','already-consumed-refresh')
    storage.set('gx_session_v1',{logged:true})
    await logout()
    assert.equal(calls.length,1)
    assert.equal(calls[0].header.Authorization,'Bearer logout-access')
    assert.deepEqual(calls[0].data,{refreshToken:'already-consumed-refresh'})
    assert.equal(request.getToken(),'');assert.equal(request.getRefreshToken(),'')
    assert.equal(storage.has('gx_session_v1'),false)
  } finally {delete globalThis.uni}
})

test('旧退出的迟到响应不能清除新登录身份，也不触发旧身份后续跳转', async () => {
  const storage=new Map();let pending
  globalThis.uni={getStorageSync:key=>storage.get(key),setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),
    request:options=>{pending=options}}
  const source=fs.readFileSync(new URL('../src/services/mobileAuth.js',import.meta.url),'utf8')
    .replace(/^import[^\n]+\n/gm,'').replace(/export /g,'')
  const {currentSessionGeneration}=await import('../src/services/sessionGeneration.mjs')
  const names=['clearTokens','commitNewSessionTokens','getToken','getRefreshToken','realRequest']
  const logout=new Function(...names,'setForcePasswordChange','currentSessionGeneration',source+'\nreturn logoutMobile')(...names.map(name=>request[name]),()=>{},currentSessionGeneration)
  try {
    request.commitNewSessionTokens('old-access','old-refresh')
    const oldLogout=logout()
    request.commitNewSessionTokens('new-access','new-refresh');storage.set('gx_session_v1',{userId:'new-user'})
    pending.success({statusCode:200,data:{code:0,data:{invalidated:true}}})
    assert.equal(await oldLogout,false)
    assert.equal(request.getToken(),'new-access');assert.equal(request.getRefreshToken(),'new-refresh')
    assert.deepEqual(storage.get('gx_session_v1'),{userId:'new-user'})
  } finally {request.clearTokens();delete globalThis.uni}
})

test('实际接口的两种版本冲突与旧业务码共用恢复分类，服务故障和拒绝优先', () => {
  for (const error of [
    {code:1,bizCode:'DATA_CONFLICT',httpStatus:400},
    {code:1,bizCode:'APPROVAL_VERSION_CONFLICT',httpStatus:409},
    {code:1,httpStatus:409},{code:409001},{code:'DATA_CONFLICT'}
  ]) assert.equal(normalizeError(error).kind,'conflict')
  assert.notEqual(normalizeError({code:1,httpStatus:400}).kind,'conflict')
  assert.equal(normalizeError({code:1,bizCode:'DATA_CONFLICT',httpStatus:500}).kind,'unknown')
  assert.equal(normalizeError({code:1,bizCode:'DATA_CONFLICT',httpStatus:403}).kind,'forbidden')
  assert.equal(normalizeError({code:1,bizCode:'DATA_CONFLICT',httpStatus:401}).kind,'auth')
})

test('新登录、换角色和失效退出清除旧身份及批次，正常令牌刷新保留当前办理上下文', async () => {
  const storage = new Map()
  globalThis.uni = {
    setStorageSync: (key, value) => storage.set(key, value),
    getStorageSync: key => storage.get(key),
    removeStorageSync: key => storage.delete(key)
  }
  const generationUrl = new URL('../src/services/sessionGeneration.mjs', import.meta.url).href
  const generation = await import(generationUrl)
  const keys = ['gx_session_v1', 'gx_internship_context_v1', 'gx_student_internship_batch_v1', 'gx_gd_teacher_batch_v1']
  const seed = () => keys.forEach(key => storage.set(key, 'previous-account'))
  storage.set('unrelated-preference', 'keep')
  seed()
  request.setToken('previous-access'); request.setRefreshToken('previous-refresh')
  const before = generation.captureSessionSnapshot(request.getToken(), request.getRefreshToken())
  request.commitNewSessionTokens('current-access', 'current-refresh')
  for (const key of keys) assert.equal(storage.has(key), false, key)
  assert.equal(request.getToken(), 'current-access')
  assert.equal(request.getRefreshToken(), 'current-refresh')
  assert.equal(generation.isSessionSnapshotCurrent(before, request.getToken(), request.getRefreshToken()), false)
  storage.set('gx_student_internship_batch_v1', 'current-batch')
  request.setToken('refreshed-access'); request.setRefreshToken('refreshed-refresh')
  assert.equal(storage.get('gx_student_internship_batch_v1'), 'current-batch')
  seed(); request.clearTokens()
  for (const key of keys) assert.equal(storage.has(key), false, key)
  assert.equal(request.getToken(), '')
  assert.equal(request.getRefreshToken(), '')
  assert.equal(storage.get('unrelated-preference'), 'keep')
  delete globalThis.uni
})
