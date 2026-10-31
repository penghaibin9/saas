import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { textbookReturnPath, textbookQueuePage, textbookQueueReturnPath } from '../src/modules/academicAffairs/components/textbooks/textbookNavigation.js'

test('教材控制台和发放两个页面的脚本与模板可独立编译', () => {
  for (const name of ['AaTextbookConsoleView', 'AaTextbookDistributionDetailView', 'AaTextbookDistributionGenerateView']) {
    const filename = new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(filename, 'utf8'), { filename: name })
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    const result = compileTemplate({ source: descriptor.template.content, filename: name, id: name, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  }
})

test('教材目录查询和翻页保留在地址中，刷新可以恢复相同结果范围', async () => {
  const routes = []
  const { state, definition } = page('AaTextbookConsoleView', { textbookQueuePage }, { $route: { query: { tab: 'catalog', catalogKeyword: '信息技术', page: '2' } }, $router: { replace: async value => routes.push(value) } })
  state.restoreCatalogQuery()
  assert.equal(state.keyword, '信息技术'); assert.equal(state.appliedKeyword, '信息技术'); assert.equal(state.page, 2)
  assert.equal(state.statusLabel('UNKNOWN_INTERNAL_STATE'), '状态待确认')
  state.reload = async () => {}
  state.initialized = true; state.openSelectionFromRoute = () => {}
  definition.watch.identityKey.call(state)
  assert.equal(state.appliedKeyword, '信息技术'); assert.equal(state.page, 2)
  state.keyword = '大学英语'; await state.search()
  assert.equal(routes[0].query.catalogKeyword, '大学英语'); assert.equal(routes[0].query.page, '1')
  await state.turnPage(2)
  assert.equal(routes[1].query.page, '2')
  await state.clearSearch()
  assert.equal(routes[2].query.catalogKeyword, undefined)
})

test('fee receivables exclude waived history while keeping actual collected amounts', () => {
  const { state } = page('AaTextbookConsoleView')
  state.tab = 'fee'; state.rows = [
    { amount: 49, paidAmount: 10, status: 'PARTIAL' },
    { amount: 46, paidAmount: 0, status: 'WAIVED' },
    { amount: 43, paidAmount: 43, status: 'PAID' }
  ]
  assert.equal(state.metricCards.find(card => card.label === '本页应收').value, '¥92.00')
  assert.equal(state.metricCards.find(card => card.label === '本页净收').value, '¥53.00')
})

test('全额退款登记冻结原实收并显示待退领，不重复计入净收', async () => {
  const calls = []
  const { state } = page('AaTextbookConsoleView', { textbookP0Api: { registerRefund: async (...args) => { calls.push(args); return { code: 0 } } } })
  state.tab = 'fee'; state.rows = [{ feeId: '3', amount: 50, paidAmount: 20, refundAmount: 20, status: 'REFUNDED' }]
  assert.equal(state.metricCards.find(card => card.label === '本页净收').value, '¥0.00')
  assert.equal(state.statusLabel('REFUNDED'), '已退款待退领')
  state.refundFee({ feeId: '3', paidAmount: 20, status: 'PARTIAL' })
  state.reload = async () => {}
  await state.onReasonConfirm({ reason: '确认实际退还全部费用' })
  assert.deepEqual(calls, [['3', '确认实际退还全部费用', 20]])
})

test('没有费用权限时统计不显示零元冒充真实结果', () => {
  const { state } = page('AaTextbookConsoleView')
  state.tab = 'stats'; state.stats = { feeVisible: false, unpaidAmount: null, refundedAmount: null }
  assert.equal(state.metricCards.some(card => card.label === '待处理费用'), false)
  assert.equal(state.statsRows.some(row => row.key === 'fee'), false)
  state.stats.feeVisible = true; state.stats.unpaidAmount = 12
  assert.equal(state.metricCards.find(card => card.label === '待处理费用').value, '¥12.00')
})

test('发放明细发现费用学生不一致时不能打开退领确认', () => {
  const { state } = page('AaTextbookDistributionDetailView', {}, { ctx: {}, $route: { params: { batchId: '7' }, query: {} } })
  state.openReturn({ recordId: '9', status: 'RECEIVED', feeMismatch: true })
  assert.equal(state.returnDialog.visible, false)
  state.openReturn({ recordId: '9', status: 'RECEIVED', feeMismatch: false })
  assert.equal(state.returnDialog.visible, true)
})

test('partial fee keeps the original paid amount on an uncertain retry and prevents duplicate clicks', async () => {
  const first = deferred(); const calls = []
  const { state } = page('AaTextbookConsoleView', {
    academicAffairsTextbookApi: { markFee: (...args) => { calls.push(args); return calls.length === 1 ? first.promise : Promise.resolve({ code: 409, message: '记录已变化，本次未再次入账' }) } }
  })
  state.tab = 'fee'
  state.openPartial({ feeId: '31', amount: 49, paidAmount: 0 })
  state.partialAmount = 10
  const pending = state.submitPartial(); await state.submitPartial()
  assert.equal(calls.length, 1)
  first.reject(new Error('网络超时')); await pending
  assert.equal(state.partialVisible, true)
  await state.submitPartial()
  assert.deepEqual(calls.map(args => [args[0], args[1], args[2], args[4]]), [['31', 'PARTIAL', 10, 0], ['31', 'PARTIAL', 10, 0]])
  assert.equal(state.saving, false)
})

test('partial fee rejects sub-cent values, excessive amounts and a changed identity', async () => {
  let writes = 0
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { markFee: async () => { writes++ } } })
  state.tab = 'fee'; state.openPartial({ feeId: '31', amount: 49, paidAmount: 10 })
  for (const value of [0.001, Infinity, -1, 40]) { state.partialAmount = value; await state.submitPartial() }
  state.partialAmount = 10; state.ctx = { changed: true }; await state.submitPartial()
  assert.equal(writes, 0)
})

test('receipt requires in-app confirmation and cannot submit after the object changes', async () => {
  const confirm = deferred(); let writes = 0
  const { state } = page('AaTextbookDistributionDetailView', {
    systemConfirm: () => confirm.promise,
    academicAffairsTextbookApi: { sign: async () => { writes++; return { code: 0 } } }
  }, { ctx: {}, $route: { params: { batchId: '7' }, query: {} } })
  const pending = state.sign({ recordId: '32', status: 'PENDING', studentName: '甲', textbookName: '教材', qty: 1 })
  assert.equal(writes, 0)
  state.$route.params.batchId = '8'
  confirm.resolve(true); await pending
  assert.equal(writes, 0)
})

test('canceling receipt confirmation does not create a fee and releases the button', async () => {
  let writes = 0
  const { state } = page('AaTextbookDistributionDetailView', {
    systemConfirm: async () => false,
    academicAffairsTextbookApi: { sign: async () => { writes++ } }
  }, { ctx: {}, $route: { params: { batchId: '7' }, query: {} } })
  await state.sign({ recordId: '32', status: 'PENDING' })
  assert.equal(writes, 0)
  assert.equal(state.acting, '')
})

test('append entry locks the original batch/class and keeps the source queue', async () => {
  let destination, sent
  const detail = page('AaTextbookDistributionDetailView', { textbookReturnPath }, {
    $route: { params: { batchId: '7' }, query: { returnTo: '/admin/academic-affairs/textbooks?tab=distribution&page=3' } },
    $router: { push: value => { destination = value } }
  })
  detail.state.loading = false; detail.state.batch = { orderBatchId: '50', classId: '4539' }
  detail.state.openAppend()
  assert.equal(destination.query.appendToBatchId, '7')
  assert.equal(destination.query.classId, '4539')
  const { state, definition } = page('AaTextbookDistributionGenerateView', { textbookReturnPath,
    academicAffairsTextbookApi: { generateDistribution: async body => { sent = body; return { code: 0, data: { distributionBatchId: '7', addedRecordCount: 2 } } } }
  }, { ctx: {}, $route: { query: destination.query }, $router: { push: value => { destination = value } } })
  definition.created.call(state)
  assert.equal(state.classId, '4539')
  state.studentIds = ['233444']; await state.submit()
  assert.equal(sent.appendToBatchId, '7')
  assert.equal(sent.classId, '4539')
  assert.equal(destination.params.batchId, '7')
  assert.equal(destination.query.returnTo, '/admin/academic-affairs/textbooks?tab=distribution&page=3')
  state.classId = '4538'
  assert.equal(state.canSubmit, false)
})

test('late append response cannot redirect a different original batch, and duplicate clicks send once', async () => {
  const pending = deferred(); let calls = 0, redirects = 0
  const { state } = page('AaTextbookDistributionGenerateView', { textbookReturnPath,
    academicAffairsTextbookApi: { generateDistribution: () => { calls++; return pending.promise } }
  }, { ctx: {}, $route: { query: { orderBatchId: '50', appendToBatchId: '7', classId: '4539' } }, $router: { push: () => { redirects++ } } })
  state.classId = '4539'; state.studentIds = ['233444']
  const operation = state.submit(); await state.submit()
  assert.equal(calls, 1)
  state.$route.query.appendToBatchId = '8'; state.resetScope()
  pending.resolve({ code: 0, data: { distributionBatchId: '7', addedRecordCount: 2 } })
  await operation
  assert.equal(redirects, 0)
  assert.equal(state.studentIds.length, 0)
  assert.equal(state.submitting, false)
})

test('distribution entry captures the current queue page and restores it in the formal API request', async () => {
  let destination, query
  const dependencies = {
    textbookQueuePage, textbookQueueReturnPath,
    academicAffairsApi: { getContext: async () => ({ code: 0, data: {} }), getCurrentTerm: async () => ({ code: 0, data: { termId: '52' } }) },
    textbookP0Api: { listDistributionBatches: async params => { query = params; return { code: 0, data: { list: [], total: 61 } } } }
  }
  const { state, definition } = page('AaTextbookConsoleView', dependencies, {
    $route: { fullPath: '/admin/academic-affairs/textbooks?tab=distribution', query: { tab: 'distribution' } },
    $router: { push: value => { destination = value } }
  })
  state.tab = 'distribution'; state.page = 3
  state.openDistribution({ distributionBatchId: '6' })
  assert.equal(destination.params.batchId, '6')
  assert.equal(destination.query.returnTo, '/admin/academic-affairs/textbooks?tab=distribution&page=3')
  const detail = page('AaTextbookDistributionDetailView', { textbookReturnPath }, { $route: { params: { batchId: '6' }, query: destination.query } })
  assert.equal(detail.state.returnPath, destination.query.returnTo)
  state.$route.query.page = '3'
  await definition.created.call(state)
  // 登录上下文响应会触发 Vue 的 identity watcher，不能把已恢复的页码重置为 1。
  definition.watch.identityKey.call(state)
  assert.equal(query.page, 3)
  assert.equal(query.termId, '52')
})

test('generation carries its original order queue through a successful write', async () => {
  let destination
  const { state } = page('AaTextbookDistributionGenerateView', {
    textbookReturnPath,
    academicAffairsTextbookApi: { generateDistribution: async () => ({ code: 0, data: { distributionBatchId: '6' } }) }
  }, { ctx: {}, $route: { query: { orderBatchId: '50', returnTo: '/admin/academic-affairs/textbooks?tab=order&page=2' } }, $router: { push: value => { destination = value } } })
  state.classId = '4538'; state.studentIds = ['233387']
  await state.submit()
  assert.equal(destination.params.batchId, '6')
  assert.equal(destination.query.returnTo, '/admin/academic-affairs/textbooks?tab=order&page=2')
})

test('textbook return links reject external addresses and unrelated business destinations', () => {
  for (const value of ['https://example.com', '//example.com', '/admin/academic-affairs/textbooks/../terms?tab=order', '/admin/academic-affairs/textbooks?tab=review', ['bad'], null]) {
    assert.equal(textbookReturnPath(value), '/admin/academic-affairs/textbooks?tab=distribution')
  }
  for (const value of ['NaN', '-1', '0', '2.5', 'Infinity', '99999999999999999']) assert.equal(textbookQueuePage(value), 1)
})

test('费用发放来源可返回原费用页，切换发放记录不携带旧申报筛选', () => {
  const original = '/admin/academic-affairs/textbooks?tab=fee&page=3'
  assert.equal(textbookReturnPath(original), original)
  let destination
  const { state } = page('AaTextbookConsoleView', {}, { $route: { query: { selectionId: '9', action: 'edit', page: '4' } }, $router: { replace: value => { destination = value } } })
  state.switchTab('distribution')
  assert.deepEqual(JSON.parse(JSON.stringify(destination.query)), { tab: 'distribution', page: '1', history: 'all' })
})

test('选用行按申报定位，同一本教材的多个任务不会选错行', () => {
  const { state } = page('AaTextbookConsoleView')
  state.tab = 'selection'
  state.rows = [{ selectionId: '11', textbookId: '7' }, { selectionId: '12', textbookId: '7' }]
  state.selectRow(state.rows[1])
  assert.equal(state.activeRowKey, '12')
  assert.equal(state.selectedObject.selectionId, '12')
})

test('本页筛选不把第三页的数据伪装成第一页', () => {
  const { state } = page('AaTextbookConsoleView')
  state.tab = 'fee'; state.page = 3; state.keyword = '教材'
  state.search()
  assert.equal(state.page, 3)
})

test('审核明细按原批次读取，旧响应不能覆盖新批次', async () => {
  const first = deferred(); const queries = []
  const { state } = page('AaTextbookConsoleView', { textbookP0Api: { reviewItems: (id, params) => {
    queries.push([id, params.page]); return id === '1' ? first.promise : Promise.resolve({ code: 0, data: { list: [{ selectionId: '22', remark: '用于实训教学' }], total: 21, batch: { reviewBatchId: '2', status: 'COLLEGE_APPROVED', actions: { advance: true } } } })
  } } })
  state.tab = 'review'
  const pending = state.openReview({ reviewBatchId: '1' })
  await state.openReview({ reviewBatchId: '2' }, 2)
  first.resolve({ code: 0, data: { list: [{ selectionId: '11' }], total: 1 } }); await pending
  assert.equal(state.reviewItems[0].selectionId, '22')
  assert.equal(state.reviewTotal, 21)
  assert.equal(state.reviewActionLabel(state.reviewRow), '学校审核并备案')
  assert.equal(state.reviewActionLabel({ status: 'DRAFT' }), '学院审核通过')
  assert.deepEqual(queries, [['1', 1], ['2', 2]])
})

test('审核明细失败显示错误并阻止以空明细冒充成功', async () => {
  const { state } = page('AaTextbookConsoleView', { textbookP0Api: { reviewItems: async () => { throw new Error('offline') } } })
  state.tab = 'review'
  await state.openReview({ reviewBatchId: '1' })
  assert.equal(state.reviewLoading, false)
  assert.match(state.reviewError, /读取失败/)
})

test('超过二百本的目录能继续分页加载且失败不保留旧目录', async () => {
  const calls = []
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: async query => {
    calls.push(query.page)
    return { code: 0, data: { list: Array.from({ length: query.page === 1 ? 200 : 1 }, (_, i) => ({ textbookId: String((query.page - 1) * 200 + i + 1) })), total: 201 } }
  } } })
  await state.openSelection()
  assert.deepEqual(calls, [1, 2]); assert.equal(state.selectionCatalog.length, 201)
  const failed = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: async () => ({ code: 403, message: '无权读取' }) } }).state
  failed.selectionCatalog = [{ textbookId: 'old' }]
  await failed.openSelection()
  assert.equal(failed.selectionCatalog.length, 0); assert.equal(failed.selectionCanSubmit, false)
})

test('到货校验整数与上下限，成功后回读并关闭已到齐批次的登记动作', async () => {
  const calls = []
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: {
    recordArrival: async (...args) => { calls.push(args); return { code: 0, data: { batchStatus: 'ARRIVED' } } },
    orderItems: async () => ({ code: 0, data: { items: [{ itemId: '8', orderQty: 3, arrivedQty: 3 }] } })
  } })
  state.tab = 'order'; state.arrivalRow = { orderBatchId: '7', status: 'PARTIALLY_ARRIVED' }
  state.arrivalItems = [{ itemId: '8', orderQty: 3, arrivedQty: 1 }]; state.reload = async () => {}
  for (const qty of [0, 1.5, 4, NaN]) { state.arrivalQty['8'] = qty; await state.submitArrival('8') }
  assert.equal(calls.length, 0)
  state.arrivalQty['8'] = 3; await state.submitArrival('8')
  assert.deepEqual(calls, [['8', 3]])
  assert.equal(state.arrivalEditable, false); assert.equal(state.arrivalItems[0].arrivedQty, 3)
})

test('编辑未定价教材不把缺失价格静默变成免费', () => {
  const { state } = page('AaTextbookConsoleView')
  state.openTextbook({ textbookId: '1', name: '待定价教材', unitPrice: null })
  assert.equal(state.tbForm.unitPrice, null)
  state.openTextbook({ textbookId: '2', name: '免费教材', unitPrice: 0 })
  assert.equal(state.tbForm.unitPrice, 0)
})

test('textbook tab pagination goes to the server', async () => {
  let query
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: async params => { query = params; return { code: 0, data: { list: [], total: 61 } } } } })
  state.page = 3
  await state.reload()
  assert.equal(query.page, 3)
  assert.equal(state.total, 61)
})

test('late catalog response cannot overwrite the fee ledger', async () => {
  const old = deferred()
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: () => old.promise } })
  const pending = state.reload()
  state.tab = 'fee'; state.rows = [{ feeId: 'fee-b' }]
  old.resolve({ code: 0, data: { list: [{ textbookId: 'old' }], total: 1 } })
  await pending
  assert.equal(state.rows[0].feeId, 'fee-b')
})

test('old distribution request cannot replace a newly selected batch', async () => {
  const old = deferred()
  const { state } = page('AaTextbookDistributionDetailView', { textbookP0Api: { distributionRecords: () => old.promise } }, { ctx: {}, $route: { params: { batchId: 'a' }, query: {} } })
  const pending = state.load()
  state.$route.params.batchId = 'b'; state.rows = [{ recordId: 'record-b' }]
  old.resolve({ code: 0, data: { list: [{ recordId: 'old' }], batch: {}, total: 1 } })
  await pending
  assert.equal(state.rows[0].recordId, 'record-b')
})

test('stock reads the canonical items envelope and keeps local paging honest', async () => {
  const rows = Array.from({ length: 23 }, (_, index) => ({ textbookId: String(index + 1), stockQty: index }))
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { stock: async () => ({ code: 0, data: { items: rows } }) } })
  state.tab = 'stock'
  await state.reload()
  assert.equal(state.total, 23)
  assert.equal(state.rows.length, 23)
  assert.equal(state.visibleRows.length, 20)
})

test('selection picker requests the complete enabled catalog for the sandbox inventory', async () => {
  let query
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: async params => { query = params; return { code: 0, data: { list: [] } } } } })
  await state.openSelection()
  assert.equal(query.status, 'ENABLED')
  assert.equal(query.page, 1)
  assert.equal(query.pageSize, 200)
})

test('selection confirmation stays locked to its original identity and tab', async () => {
  let submits = 0
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { submitSelection: async () => { submits += 1; return { code: 0, data: {} } } } })
  state.tab = 'selection'
  state.confirmSelectionSubmit({ selectionId: '17', courseName: '软件测试' })
  state.tab = 'review'
  state.onConfirm()
  await Promise.resolve()
  assert.equal(submits, 0)
})

test('teacher textbook edit normalizes the route only after the write guard is released', async () => {
  const record = { selectionId: '301', taskId: '19', textbookId: '21', expectedQty: 30, remark: '教学使用教材', courseName: '课程甲', status: 'DRAFT' }
  const { state, definition } = page('AaTextbookConsoleView', {
    academicAffairsTextbookApi: {
      updateSelection: async () => ({ code: 0, data: record }),
      listSelections: async () => ({ code: 0, data: { list: [record], total: 1 } })
    }
  }, {
    $route: { path: '/admin/academic-affairs/textbooks', query: { tab: 'selection', selectionId: '301', action: 'edit' }, params: {} }
  })
  state.ctx = { currentRole: { roleCode: 'ACADEMIC_TEACHER' } }
  state.tab = 'selection'; state.editingSelectionId = '301'; state.selectionVisible = true
  state.selectionForm = { taskId: '19', textbookId: '21', expectedQty: 30, remark: '教学使用教材' }
  const savingStates = []
  state.$router.replace = async target => {
    savingStates.push(state.saving)
    assert.equal(definition.beforeRouteUpdate.call(state), true)
    state.$route.query = target.query
  }
  await state.submitSelection()
  assert.deepEqual(savingStates, [false])
  assert.equal(state.$route.query.action, undefined)
  assert.equal(state.selectionVisible, false)
  assert.equal(state.selectionDraftReceipt.id, '301')
})

test('teacher task deep link retries the same formal task after a read failure', async () => {
  const queries = []
  const { state } = page('AaTextbookConsoleView', {
    academicAffairsApi: { listAllTasks: async query => {
      queries.push(query)
      if (queries.length === 1) throw new Error('Failed to fetch')
      return { code: 0, data: { list: [{ taskId: '19', status: 'READY', expectedStudents: 30 }] } }
    } },
    academicAffairsTextbookApi: {
      listSelections: async () => ({ code: 0, data: { list: [], total: 0 } }),
      listTextbooks: async () => ({ code: 0, data: { list: [] } })
    }
  }, { $route: { query: { tab: 'selection', action: 'create', taskId: '19' } } })
  state.ctx = { currentRole: { roleCode: 'ACADEMIC_TEACHER' } }
  state.tab = 'selection'; state.currentTermId = '52'
  await state.openSelectionFromRoute()
  assert.equal(state.error, '教学任务读取失败，请重试')
  assert.equal(state.selectionVisible, false)
  await state.retryLoad()
  assert.equal(state.error, '')
  assert.equal(queries.length, 2)
  assert.ok(queries.every(query => query.taskId === '19' && query.termId === '52' && query.formalMine))
  assert.equal(state.selectionVisible, true)
  assert.equal(state.selectionForm.taskId, '19')
  assert.equal(state.selectionForm.expectedQty, 30)
})

test('late teacher task deep link response cannot open a different task', async () => {
  const old = deferred()
  const { state } = page('AaTextbookConsoleView', {
    academicAffairsApi: { listAllTasks: () => old.promise }
  }, { $route: { query: { tab: 'selection', action: 'create', taskId: '19' } } })
  state.ctx = { currentRole: { roleCode: 'ACADEMIC_TEACHER' } }
  state.tab = 'selection'; state.currentTermId = '52'
  const pending = state.openSelectionFromRoute()
  state.$route.query.taskId = '20'
  old.resolve({ code: 0, data: { list: [{ taskId: '19', status: 'READY' }] } })
  await pending
  assert.equal(state.selectionVisible, false)
  assert.equal(state.openedSetupTaskId, '')
})

test('returned selection deep link rereads and edits the original selection and teaching task', async () => {
  let query, updatedId
  const record = { selectionId: '301', taskId: '19', textbookId: '21', expectedQty: 30, remark: '教学使用教材', status: 'RETURNED', rejectReason: '请核对教材版本' }
  const { state } = page('AaTextbookConsoleView', {
    academicAffairsTextbookApi: {
      listSelections: async params => { query = params; return { code: 0, data: { list: [record], total: 1 } } },
      listTextbooks: async () => ({ code: 0, data: { list: [] } }),
      updateSelection: async id => { updatedId = id; return { code: 0, data: { ...record, status: 'DRAFT' } } }
    }
  }, { $route: { path: '/admin/academic-affairs/textbooks', query: { tab: 'selection', selectionId: '301', action: 'edit' } } })
  state.ctx = { currentRole: { roleCode: 'ACADEMIC_TEACHER' } }
  state.tab = 'selection'; state.currentTermId = '52'
  await state.reload()
  assert.equal(query.selectionId, '301')
  assert.equal(query.termId, '52')
  assert.equal(state.activeRowKey, '301')
  assert.equal(state.selectedObject.rejectReason, '请核对教材版本')
  assert.equal(state.editingSelectionId, '301')
  assert.equal(state.selectionForm.taskId, '19')
  state.$router.replace = async target => { state.$route.query = target.query }
  await state.submitSelection()
  assert.equal(updatedId, '301')
  assert.equal(state.selectionDraftReceipt.id, '301')
})

test('review buttons and creation use only server actions, and creation selects one source college', async () => {
  let submitted
  const { state } = page('AaTextbookConsoleView', {
    textbookP0Api: {
      listReviewBatches: async () => ({ code: 0, data: { list: [{ reviewBatchId: '6', status: 'DRAFT', actions: { advance: false, return: false } }], total: 1, actions: { createReview: true } } }),
      reviewCandidates: async () => ({ code: 0, data: { items: [
        { selectionId: '11', collegeId: '7', collegeName: '学院甲' },
        { selectionId: '12', collegeId: '8', collegeName: '学院乙' }
      ] } })
    },
    academicAffairsTextbookApi: { createReviewBatch: async body => { submitted = body; return { code: 0 } } }
  })
  state.tab = 'review'; state.currentTermId = '52'
  await state.reload()
  assert.equal(state.canAdvance(state.rows[0]), false)
  assert.equal(state.canAdvance({ status: 'PUBLISHED', actions: { advance: true } }), true)
  assert.equal(state.canAdvance({ status: 'DRAFT' }), false)
  await state.createReview()
  assert.equal(state.reviewCreateVisible, true)
  assert.equal(state.reviewCollegeId, '')
  await state.submitReview()
  assert.equal(submitted, undefined)
  state.reviewCollegeId = '8'
  await state.submitReview()
  assert.deepEqual(Array.from(submitted.selectionIds), ['12'])
  assert.equal(submitted.termId, '52')
})
test('已提交教材选用显示审核岗接手，并保留教师填写的课程名称',()=>{
  const {state}=page('AaTextbookConsoleView');state.tab='selection';state.rows=[{selectionId:'1',courseName:'PUBLIC_BASIC',status:'SUBMITTED',officerName:'同名教师',officerLoginName:'teacher-a'}]
  assert.equal(state.normalizedRows[0].primary,'PUBLIC_BASIC')
  assert.equal(state.normalizedRows[0].currentOwner,'教材选用审核岗')
  assert.equal(state.normalizedRows[0].nextOwner,'审核通过后交征订岗位')
  assert.equal(state.normalizedRows[0].officerLoginName,'teacher-a')
  assert.equal(state.statusLabel('UNKNOWN_INTERNAL'),'状态待确认')
})
test('教材目录筛选总量与本页数量有独立明确口径',()=>{
  const {state}=page('AaTextbookConsoleView');state.tab='catalog';state.total=196;state.rows=[{status:'ENABLED',unitPrice:40,isbn:'book',publisher:'press'}]
  assert.equal(state.metricCards[0].label,'目录总数');assert.equal(state.metricCards[0].value,196)
  assert.equal(state.metricCards[1].label,'本页在用');assert.equal(state.metricCards[1].value,1)
  state.appliedKeyword='信息技术';state.total=2;assert.equal(state.metricCards[0].label,'筛选结果总数');assert.equal(state.metricCards[0].value,2)
})
