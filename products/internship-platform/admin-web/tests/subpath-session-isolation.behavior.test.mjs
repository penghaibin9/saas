import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

test('独立子路径的账号清理与退出不删除同域旧系统令牌和草稿', async () => {
  const values = new Map(['gx_pc_token_v1','gx_pc_refresh_v1','sp_token_v1','sp_refresh_v1','sp_gd_temp_files_v1','student_portal_report_draft_v1','student_portal_internship_batch_v1'].map(key=>[key,'other-system-data']))
  const session = new Map()
  const previous = { localStorage:globalThis.localStorage, sessionStorage:globalThis.sessionStorage }
  const storage = map => ({getItem:key=>map.get(key)||null,setItem:(key,value)=>map.set(key,value),removeItem:key=>map.delete(key)})
  globalThis.localStorage=storage(values); globalThis.sessionStorage=storage(session)
  try {
    for (const path of ['../src/services/http/client.js','../../student-web/src/services/request.js','../../enterprise-web/src/services/request.js']) {
      let source=fs.readFileSync(new URL(path,import.meta.url),'utf8').replace(/^import .*$/gm,'')
      source=source.replaceAll('import.meta.env','({VITE_STORAGE_SCOPE:"internship",VITE_API_BASE_URL:"/internship",BASE_URL:"/internship/",DEV:false})')
      source='const API_BASE_URL="/internship",API_PREFIX_INJECTED="/api/v1";const toast=()=>{},normalizeUiError=e=>e,allowMockFallback=()=>false,realApiEnabled=()=>true;'+source
      if(path.includes('/http/'))source='const API_PREFIX="/api/v1";'+source
      const client=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
      client.clearSession?.();client.clearAuthSession?.()
      if(client.setTenantCode){client.setTenantCode('school');client.setSelectedCampaignId('17');assert.equal(session.get('internship:ep_tenant_code_v1'),'school');assert.equal(session.get('internship:ep_campaign_id_v1'),'17')}
    }
    assert.equal(values.size,7)
    assert.ok([...values.values()].every(value=>value==='other-system-data'))
  } finally {
    for(const [key,value] of Object.entries(previous)){if(value===undefined)delete globalThis[key];else globalThis[key]=value}
  }
})
