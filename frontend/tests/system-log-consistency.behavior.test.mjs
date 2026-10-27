import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { formatDateTime } from '../src/utils/dateUtils.js'
import { roleDisplayLabel } from '../src/modules/system/utils/permissionLabels.js'
import { presentAuditRecord } from '../src/utils/presentationSafety.js'

process.env.TZ = 'Asia/Shanghai'
test('audit summaries preserve Chinese actions and name authentication events', () => {
  assert.equal(presentAuditRecord({action:'保存角色权限'}).displayAction,'保存角色权限')
  assert.equal(presentAuditRecord({action:'TOKEN_REFRESH'}).displayAction,'会话刷新')
  assert.equal(presentAuditRecord({action:'PERMISSION_DENIED'}).displayAction,'越权拦截')
})
test('the school time zone wins over the browser time zone', () => {
  const previous=process.env.TZ
  process.env.TZ='UTC'
  try {
    assert.equal(formatDateTime('2026-10-24T16:00:00Z','', 'Asia/Shanghai'),'2026-10-25 00:00')
    assert.equal(formatDateTime('2026-10-24T16:00:00Z','', 'UTC+08:00'),'2026-10-25 00:00')
  } finally { process.env.TZ=previous }
})
test('evidence gaps name the missing actor, trace, reason and version fields', () => {
  const source=readFileSync(new URL('../src/modules/system/views/SystemAuditView.vue',import.meta.url),'utf8')
  const declaration=source.match(/const FIELD_LABELS = [^\r\n]+/)[0]
  const method=source.match(/fieldLabel\(value\) \{[^\r\n]+\}/)[0]
  const label=Function(`${declaration}; return ({${method}}).fieldLabel`)()
  assert.deepEqual(['actorId','traceId','reason','version','tenantId','object'].map(label),['操作人','请求编号','操作原因','版本信息','学校范围','业务对象'])
})
const source = readFileSync(new URL('../src/modules/system/api/system.api.js', import.meta.url), 'utf8').replace(/\r\n/g, '\n')
test('audit export forwards queried filters and chosen columns with a download timeout', async () => {
  const method = source.match(/  async exportLogs\([\s\S]*?^  },/m)[0]
  let captured
  const run = Function('requestBlob', 'saveBlob', 'now', 'ok', 'apiError', `return ({${method}}).exportLogs`)(
    async (path, options) => { captured = { path, options }; return 'file' }, () => {},
    () => '2026-10-25', data => data, error => { throw error })
  await run({ tab: 'operation', filters: { module:'internship', action:'USER_UPDATE', dateFrom:'2026-10-01' },
    fields:[{key:'time',checked:true},{key:'result',checked:true}], scope:'FILTERED' })
  assert.equal(captured.path, '/system/export/logs')
  assert.deepEqual(captured.options.params, { module:'internship', action:'USER_UPDATE', dateFrom:'2026-10-01',
    tab:'operation', fields:'time,result', scope:'FILTERED' })
  assert.equal(captured.options.timeoutMs, 60000)
})
function clientMethod(name, request) {
  const method = source.match(new RegExp(`  async ${name}\\([\\s\\S]*?^  },`, 'm'))[0]
  const helper = source.match(/function logPage\(data\) \{[\s\S]*?\n\}/)[0]
  return Function('request', 'formatDateTime', `const ok=data=>({code:0,data}); const fail=message=>({code:1,message}); ${helper};return ({${method}}).${name}`)(request, formatDateTime)
}

test('login, operation and sensitive logs display the same local instant and keep original results', async () => {
  for (const name of ['getLoginLogs', 'getOperationLogs', 'listSensitiveLogs']) {
    const method = clientMethod(name, async () => ({ list: [{ id:'9007199254740999', time:'2026-10-24T16:00:00Z', result:'DENIED', resultLabel:'越权拦截' }], total:251 }))
    const result = await method({})
    assert.equal(result.data.list[0].time, '2026-10-25 00:00')
    assert.equal(result.data.list[0].result, 'DENIED')
    assert.equal(result.data.list[0].id, '9007199254740999')
    assert.equal(result.data.total, 251)
  }
})

test('account login time and audit evidence use the common time formatter', async () => {
  const instant = '2026-10-25T08:58:00Z'
  const account = await clientMethod('getUsers', async () => ({list:[{lastLoginAt:instant},{lastLoginAt:null}]}))({})
  assert.equal(account.data.list[0].lastLoginAt, '2026-10-25 16:58')
  assert.equal(account.data.list[1].lastLoginAt, '')
  const evidence = await clientMethod('getAuditEvidence', async () => ({items:[{occurredAt:instant, resultNote:'原记录不一致'}]}))({})
  assert.equal(evidence.data.items[0].occurredAt, '2026-10-25 16:58')
  assert.equal(evidence.data.items[0].resultNote, '原记录不一致')
})

test('log filters retain their exact page and criteria in the server request', async () => {
  let sent
  const method = clientMethod('getOperationLogs', async (path, options) => { sent={path,...options}; return {list:[],total:0} })
  await method({keyword:'核对',module:'graduationDesign',result:'DENIED',dateFrom:'2026-10-25',dateTo:'2026-10-25',page:3,pageSize:10})
  assert.equal(sent.params.module, 'graduationDesign')
  assert.equal(sent.params.result, 'DENIED')
  assert.equal(sent.params.date_from, '2026-10-25')
  assert.equal(sent.params.page, 3)
})

const vue = readFileSync(new URL('../src/modules/system/views/SystemLogView.vue', import.meta.url),'utf8')
const {descriptor}=parse(vue)
test('switching log tabs ignores late responses and displays real role names', async () => {
  const env = { roleDisplayLabel, systemApi:{}, AppDrawer:{}, ExportDialog:{} }
  for (const name of ['ModulePageShell','ModuleToolbar','AdvancedFilter','DataTable','StatusTag','LoadingState','ErrorState','EmptyState']) env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm,'').replace('export default','globalThis.component ='),env)
  const component=env.component
  const state={...component.data(),tab:'operation'}
  let finishOld
  Object.assign(env.systemApi,{getOperationLogs:()=>new Promise(resolve=>{finishOld=resolve}),getLoginLogs:async()=>({code:0,data:{list:[{id:'login'}],total:1}})})
  const old=component.methods.load.call(state)
  state.tab='login'
  await component.methods.load.call(state)
  finishOld({code:0,data:{list:[{id:'old-operation'}],total:99}})
  await old
  assert.equal(state.rows[0].id,'login')
  assert.equal(state.pagination.total,1)
  assert.equal(component.methods.roleLabel('SYS_ADMIN'),'系统管理员')
  assert.equal(component.methods.roleLabel('—'),'未记录身份')
  assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'SystemLogView.vue',id:'log'}).errors,[])
})
