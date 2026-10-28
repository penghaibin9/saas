import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
test('正常登录成功后先清旧学校批次及草稿，再建立新学生会话',async()=>{
  const source=fs.readFileSync(new URL('../src/stores/session.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const useSessionStore','const useSessionStore')
  const cache=new Map([['batch','旧学校批次'],['draft','旧学生草稿']]),events=[]
  let data={accessToken:'synthetic-token',tenantId:'2',user:{id:'3',userType:'STUDENT',realName:'新虚构学生'}}
  const deps={defineStore:(_name,value)=>value,portalApi:{login:async()=>data},clearSession:()=>{cache.clear();events.push('clear')},getToken:()=>'',request(){},setRefreshToken(){},setToken:()=>events.push('new-session')}
  const definition=new Function(...Object.keys(deps),source+'\nreturn useSessionStore')(...Object.values(deps));const state={...definition.state(),...definition.actions}
  await state.login('student','synthetic-only','school');assert.deepEqual(events,['clear','new-session']);assert.equal(cache.size,0);assert.equal(state.user.tenantId,'2')
  data={user:{userType:'TEACHER'}};events.length=0;await assert.rejects(()=>state.login('teacher','synthetic-only','school'),/学生账号/);assert.deepEqual(events,[])
})
