import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { reactive } from 'vue'

const okList = (list = []) => ({ code: 0, data: { list, total: list.length } })

test('本人办理后任务离开当前筛选时只清对象定位，保留原页和筛选',async()=>{
  const routes=[];const {state}=page('AaQualityDashboardView',{},{$route:{path:'/quality',query:{tab:'followUp',rectId:'146',page:'2',returnToken:'source'}},$router:{replace:async route=>routes.push(route)}})
  state.tab='followUp';state.actionNotice='已关闭';state.loadRectifications=async()=>{}
  await state.refreshRectQueueAfterWrite({rectId:'146',status:'CLOSED'})
  assert.equal(routes[0].query.rectId,undefined);assert.equal(routes[0].query.page,'2');assert.equal(routes[0].query.returnToken,'source')
  state.rectStatusFilter='ALL';await state.refreshRectQueueAfterWrite({rectId:'146',status:'CLOSED'});assert.equal(routes.length,1)
  state.rectStatusFilter='IN_PROGRESS';await state.refreshRectQueueAfterWrite({rectId:'146',status:'SUBMITTED'});assert.equal(routes.length,2)
})

test('只有正式详情明确允许复核才可打开；提交前权限失效不发送写入',async()=>{
  let writes=0
  const row={rectId:'146',status:'SUBMITTED',reviewAllowed:true,title:'虚构整改'}
  const {state}=page('AaQualityDashboardView',{academicAffairsQualityApi:{getRectification:async()=>({code:0,data:{...row,reviewAllowed:false}}),reviewRectification:async()=>{writes++}}})
  state.tab='followUp';state.openReview({...row,reviewAllowed:false},'APPROVE');assert.equal(state.reviewVisible,false)
  state.openReview(row,'APPROVE');await state.submitReview();assert.equal(writes,0);assert.match(state.rectFormError,/无权/)
})

test('整改进度日志按服务端UTC解释旧值，显示本地办理时间',()=>{
  const previous=process.env.TZ;process.env.TZ='Asia/Shanghai'
  try{const {state}=page('AaQualityDashboardView');assert.equal(state.timelineFromLog([{time:'2026-10-27T07:51:32',action:'CREATE'}])[0].time,'2026-10-27 15:51')}
  finally{if(previous===undefined)delete process.env.TZ;else process.env.TZ=previous}
})

test('真实响应式状态仍识别同一次创建回执，不永久锁在待核实', async () => {
  let writes=0, reads=0
  const record={recordId:'581',recordType:'INSPECTION',title:'虚构检查',status:'SUBMITTED'}
  const {state}=page('AaQualityDashboardView',{academicAffairsQualityApi:{
    createRecord:async()=>{writes++;return {code:0,data:record}},
    getRecord:async()=>{reads++;return {code:0,data:record}},listRecords:async()=>okList([record])
  }})
  const actual=reactive(state);actual.tab='inspection';actual.recForm={collegeId:'128',title:'虚构检查',description:'仅用于流程回归'}
  await actual.submitRecCreate()
  assert.equal(writes,1);assert.equal(reads,1);assert.equal(actual.pendingWrite,null);assert.equal(actual.actionReceipt.verified,true)
  const original={identity:actual.identityKey,tab:actual.tab};actual.pendingWrite=original
  assert.equal(actual.currentWrite(original),true)
  assert.equal(actual.currentWrite({...original}),false,'另一笔相同内容的操作不能借用回执')
})

test('late evaluation results cannot replace another batch', async () => {
  const old = deferred()
  const { state } = page('AaEvaluationConsoleView', { academicAffairsEvaluationApi: { results: () => old.promise } })
  state.current = { batchId: 'a' }
  const pending = state.loadCurrentResults()
  state.current = { batchId: 'b' }; state.results = [{ resultId: 'b' }]
  old.resolve({ code: 0, data: { list: [{ resultId: 'a' }], total: 1 } })
  await pending
  assert.equal(state.results[0].resultId, 'b')
})

test('failed quality record request is visible as an error, not an empty list', async () => {
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: { listRecords: async () => ({ code: 503001, message: '服务不可用' }) } })
  state.tab = 'inspection'
  await state.loadRecords()
  assert.equal(state.panelError, '服务不可用')
})

test('未关闭整改在请求分页前筛选，不把全部记录总数当待办总数',async()=>{
  const calls=[]
  const {state}=page('AaQualityDashboardView',{academicAffairsQualityApi:{
    listRectifications:async params=>{calls.push(params);return {code:0,data:{list:[],total:0}}},
    listRecords:async()=>okList([])
  }})
  state.tab='followUp';state.rectPagination.page=2
  await state.loadRectifications()
  assert.equal(calls[0].status,'NOT_CLOSED');assert.equal(calls[0].page,2)
  state.rectStatusFilter='CLOSED'
  await state.loadRectifications()
  assert.equal(calls[1].status,'CLOSED')
  state.rectStatusFilter='ALL'
  await state.loadRectifications()
  assert.equal(calls[2].status,undefined)
})

test('AA-226 through AA-233 keep eight distinct business workspaces', () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaQualityDashboardView.vue', import.meta.url), 'utf8')
  for (const title of ['质量看板', '督导听课', '巡课记录', '教学检查', '教学事故', '质量整改', '整改跟进', '质量归档']) assert.match(source, new RegExp(`title: '${title}'`))
  for (const layout of ['aaql-overview-layout', 'aaql-form--record', 'aaql-kanban', 'aaql-follow-layout', 'archiveRows']) assert.match(source, new RegExp(layout))
})

test('整改末页关闭后返回有效页，空队列与失败都不残留上次对象', async () => {
  const routes = []
  let fail = false
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRectifications: async () => fail ? { code: 503001, message: '暂时无法读取' } : { code: 0, data: { list: [], total: 0 } },
    listRecords: async () => okList([])
  } }, { $route: { query: { page: '2', returnToken: 'source' } }, $router: { replace: async value => routes.push(value) } })
  state.tab = 'followUp'; state.rectPagination.page = 2; state.rectCurrent = { rectId: 'old', status: 'PENDING' }
  await state.loadRectifications()
  assert.equal(routes[0].query.page, '1')
  assert.equal(routes[0].query.returnToken, 'source')
  assert.equal(state.rectCurrent, null)
  state.rectPagination.page = 1; state.rectCurrent = { rectId: 'old' }; fail = true
  await state.loadRectifications()
  assert.equal(state.rectCurrent, null)
  assert.equal(state.rectRows.length, 0)
  assert.match(state.panelError, /暂时无法读取/)
})

test('整改筛选和分页写入页面地址，刷新回读不变成另一队列', () => {
  const routes = []
  const { state } = page('AaQualityDashboardView', {}, { $route: { query: { tab: 'followUp', page: '2', rectStatus: 'ALL' } }, $router: { replace: value => routes.push(value) } })
  state.tab = 'followUp'; state.loadRectifications = () => {}
  state.afterTabLoad()
  assert.equal(state.rectStatusFilter, 'ALL'); assert.equal(state.rectPagination.page, 2)
  state.rectStatusFilter = 'CLOSED'; state.searchRectifications()
  assert.equal(routes[0].query.rectStatus, 'CLOSED'); assert.equal(routes[0].query.page, '1')
  state.$route.query.rectStatus = 'INVALID'; state.afterTabLoad()
  assert.equal(state.rectStatusFilter, '')
})

test('rectification is created only from the frozen confirmed source record and read back', async () => {
  const source = { recordId: 31, recordType: 'INSPECTION', status: 'CONFIRMED', title: '期中材料检查', createdAt: '2026-09-09T09:00:00' }
  let called = 0
  const quality = {
    getRecord: async () => ({ code: 0, data: { ...source } }),
    rectifyFromRecord: async (recordId, body) => { called++; assert.equal(String(recordId), '31'); assert.equal(body.title, '期中材料检查整改'); return { code: 0, data: { rectId: 81 } } },
    getRectification: async () => ({ code: 0, data: { rectId: 81, sourceRecordId: 31, title: '期中材料检查整改', status: 'PENDING', responsibleName: '王老师' } }),
    listRectifications: async () => okList([]),
    listRecords: async () => okList([source])
  }
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: quality })
  state.tab = 'rectify'; state.rectSourceRecord = Object.freeze({ ...source }); state.rectForm = { title: '期中材料检查整改', requirement: '三日内补齐检查材料' }
  await state.submitRectCreate()
  assert.equal(called, 1)
  assert.equal(state.pendingWrite, null)
  assert.equal(state.actionReceipt.verified, true)
  assert.match(state.actionNotice, /正式整改状态/)
})

test('record confirmation refuses a changed object before issuing the command', async () => {
  const row = { recordId: 9, recordType: 'PATROL', status: 'SUBMITTED', title: '第一节巡课', createdAt: '2026-09-09T08:00:00' }
  let writes = 0
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    getRecord: async () => ({ code: 0, data: { ...row, title: '已被他人修改' } }),
    confirmRecord: async () => { writes++; return { code: 0 } }
  } })
  state.tab = 'patrol'
  await state.confirmRec(row)
  assert.equal(writes, 0)
  assert.equal(state.pendingWrite, null)
  assert.equal(state.actionNotice, '')
})

test('an ambiguous progress response stays locked and read-only verification never replays it', async () => {
  const before = { rectId: 72, sourceRecordId: 31, status: 'PENDING', title: '课堂整改', createdAt: '2026-09-09T09:00:00', progressLog: [] }
  const after = { ...before, status: 'IN_PROGRESS', progressLog: [{ action: 'PROGRESS', note: '已完成第一轮整改' }] }
  let reads = 0, writes = 0
  const quality = {
    getRectification: async () => ({ code: 0, data: reads++ === 0 ? { ...before } : { ...after } }),
    addProgress: async () => { writes++; return { code: -1, message: '网络超时' } },
    listRectifications: async () => okList([after]),
    listRecords: async () => okList([])
  }
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: quality })
  state.tab = 'followUp'; state.openProgress(before); state.rectNoteText = '已完成第一轮整改'
  await state.submitRectNote()
  assert.equal(writes, 1)
  assert.ok(state.pendingWrite)
  await state.verifyPendingWrite()
  assert.equal(writes, 1)
  assert.equal(state.pendingWrite, null)
  assert.equal(state.actionReceipt.verified, true)
})

test('rectification queue keeps successful data visible when source lookup partially fails', async () => {
  const rows = [{ rectId: 4, status: 'PENDING', title: '整改任务' }]
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRectifications: async () => okList(rows),
    listRecords: async () => ({ code: 503001, message: '来源服务不可用' })
  } })
  state.tab = 'rectify'
  await state.loadRectifications()
  assert.equal(state.rectRows.length, 1)
  assert.equal(state.panelError, '')
  assert.match(state.rectPartial, /来源服务不可用/)
})

test('archive composes traceable evidence rows and labels partial success honestly', async () => {
  const record = { recordId: 7, recordType: 'SUPERVISION', status: 'CLOSED', title: '课堂观察', conclusion: '完成改进', confirmedAt: '2026-09-09T10:00:00' }
  const rect = { rectId: 8, sourceRecordId: 7, sourceType: 'SUPERVISION', sourceTitle: '课堂观察', title: '课堂观察整改', resultNote: '复核通过', status: 'CLOSED', closedAt: '2026-09-09T11:00:00', progressLog: [{ action: 'APPROVE', note: '达到要求' }] }
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    archiveOverview: async () => ({ code: 503001, message: '汇总暂不可用' }),
    listRecords: async () => okList([record]),
    listRectifications: async () => okList([rect])
  } })
  await state.loadArchive()
  assert.equal(state.panelError, '')
  assert.match(state.archivePartial, /汇总暂不可用/)
  assert.equal(state.archiveRows.length, 1)
  assert.equal(state.archiveRows[0].sourceTitle, '课堂观察')
  assert.equal(state.archiveRows[0].conclusion, '复核通过')
  assert.equal(state.archiveRows[0].timeline[0].title, '复核通过')
})

test('403 clears quality scope data instead of leaving a stale queue', async () => {
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRectifications: async () => ({ code: 403, message: '禁止访问' }),
    listRecords: async () => okList([])
  } })
  state.tab = 'rectify'; state.rectRows = [{ rectId: 1 }]
  await state.loadRectifications()
  assert.equal(state.rectRows.length, 0)
  assert.match(state.panelError, /无权/)
})
