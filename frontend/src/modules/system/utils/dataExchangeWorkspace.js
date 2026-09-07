/** Task-centre presentation and request lifecycle. All authority remains server-side. */
export const EXCHANGE_READ = Object.freeze([
  'systemAdmin.dataExchange.viewOwn', 'systemAdmin.dataExchange.viewTenant',
  'systemAdmin.user.import', 'systemAdmin.migration.view',
  'academicAffairs.roster.import', 'academicAffairs.grade.import', 'academicAffairs.schedule.import'
])
const ACADEMIC = ['academicAffairs.roster.import', 'academicAffairs.grade.import', 'academicAffairs.schedule.import']
export function exchangeRights(has) {
  const any = codes => codes.some(has)
  return {
    read: any(EXCHANGE_READ), upload: has('systemAdmin.user.import'),
    migration: has('systemAdmin.migration.view'),
    confirm: any(['systemAdmin.dataExchange.confirm', 'systemAdmin.user.import', 'systemAdmin.migration.import', ...ACADEMIC]),
    retry: any(['systemAdmin.dataExchange.retry', 'systemAdmin.user.import', 'systemAdmin.migration.import', ...ACADEMIC]),
    download: any(['systemAdmin.dataExchange.download', 'systemAdmin.user.import', ...ACADEMIC]),
    revoke: any(['systemAdmin.dataExchange.revoke', 'systemAdmin.user.import']),
    // A viewTenant-only subject cannot send OWN: the backend does not imply that grant.
    initialVisibility: any(EXCHANGE_READ.filter(code => code !== 'systemAdmin.dataExchange.viewTenant')) ? 'OWN' : 'TENANT'
  }
}
export const TASK_STATUSES = Object.freeze({
  SCANNING: '安全扫描中', WORKER_CLAIMED: '后台已领取', PARSING: '服务端预检中',
  VALIDATED: '预检通过 · 待确认', VALIDATION_FAILED: '预检未通过', CONFIRMING: '正在确认',
  CREATED: '等待生成', RUNNING: '正在生成', SUCCEEDED: '已完成', FAILED: '处理失败',
  CANCELLED: '已取消', EXPIRED: '已过期', REVOKED: '已撤销'
})
export const TASK_LABELS = Object.freeze({
  IDENTITY_STUDENT: '学生导入与账号开通', IDENTITY_TEACHER: '教职工导入',
  ACADEMIC_ROSTER: '教务名册导入', ACADEMIC_GRADE: '教务成绩导入', ACADEMIC_SCHEDULE: '教务排课导入',
  ACADEMIC_PROGRAM: '培养方案导入', ACADEMIC_COURSE_CATALOG: '课程库导入',
  IMPORT_ERROR_RECEIPT: '导入错误回执', INITIAL_CREDENTIAL_RECEIPT: '初始账号凭据回执'
})
const PREVIEW_READY = new Set(['VALIDATED', 'VALIDATION_FAILED', 'CONFIRMING', 'SUCCEEDED'])
const number = value => Number.isSafeInteger(value) && value >= 0
export const taskCount = value => number(value) ? String(value) : '未取得'
export const taskStatus = row => TASK_STATUSES[row?.status] || '状态待核对'
export const taskLabel = row => TASK_LABELS[row?.importType || row?.exportType] || (row?.jobType === 'EXPORT' ? '导出任务' : '导入任务')
export function taskId(id) {
  if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id)) throw new Error('任务编号无效，请从任务列表重新选择')
  return id
}
export function taskRef(row) {
  if (!['IMPORT', 'EXPORT'].includes(row?.jobType)) throw new Error('任务类型未取得，不能混用导入与导出编号')
  return { id: taskId(row.id), jobType: row.jobType }
}
export const taskKey = row => `${taskRef(row).jobType}:${row.id}`
export function assertTask(row, ref) {
  taskRef(row)
  if ((ref && taskKey(row) !== taskKey(ref)) || !number(row.version) || typeof row.status !== 'string' || typeof row.moduleCode !== 'string') {
    throw new Error('任务类型、编号或版本与当前选择不一致')
  }
  if (row.receiptJobs != null) {
    const receipts = row.receiptJobs
    if (row.jobType !== 'IMPORT' || !Array.isArray(receipts.list) || !number(receipts.total)
      || receipts.total < receipts.list.length || receipts.list.some(item => item.jobType !== 'EXPORT'
        || item.moduleCode !== row.moduleCode || item.adapterType !== 'IMPORT_JOB'
        || item.adapterRef !== row.id || !number(item.version))) throw new Error('关联回执元数据不完整')
    for (const item of receipts.list) taskRef(item)
  }
  return row
}
export function taskCounts(row) {
  const ready = row?.jobType === 'IMPORT' ? PREVIEW_READY.has(row.status) : ['SUCCEEDED', 'EXPIRED', 'REVOKED'].includes(row?.status)
  const keys = row?.jobType === 'IMPORT' ? ['totalRows', 'validRows', 'invalidRows'] : ['rowCount', 'downloadedCount']
  return Object.fromEntries(keys.map(key => [key, ready && number(row[key]) ? row[key] : null]))
}
export function actionAvailable(type, row, rights) {
  if (!row || !number(row.version)) return false
  if (type === 'confirm') {
    // Identity tasks must be atomic. Partial academic schedules stay in their domain UI.
    const counts = taskCounts(row)
    return !!rights.confirm && row.jobType === 'IMPORT' && row.status === 'VALIDATED'
      && number(counts.totalRows) && number(counts.validRows) && counts.validRows > 0
      && counts.invalidRows === 0 && counts.totalRows === counts.validRows
  }
  if (type === 'retry') return !!rights.retry && row.jobType === 'IMPORT' && row.retryable === true && ['VALIDATION_FAILED', 'FAILED'].includes(row.status)
  if (type === 'cancel') return !!rights.confirm && row.jobType === 'IMPORT' && row.cancellable === true && ['SCANNING', 'PARSING', 'VALIDATED', 'VALIDATION_FAILED', 'FAILED'].includes(row.status)
  if (type === 'download') return !!rights.download && row.jobType === 'EXPORT' && row.status === 'SUCCEEDED' && row.downloadable === true && !!row.fileObjectId
  if (type === 'revoke') return !!rights.revoke && row.jobType === 'EXPORT' && row.status === 'SUCCEEDED'
  return false
}
export function taskFingerprint(row) {
  return JSON.stringify([taskKey(row), row.moduleCode, row.version, row.status, row.importType, row.exportType,
    row.sourceFileId, row.fileObjectId, row.totalRows, row.validRows, row.invalidRows,
    row.retryable, row.cancellable, row.downloadable, row.strongSensitive])
}
function responseContext(data, context) {
  if (!data || data.visibility !== context.visibility || (context.visibility === 'MODULE' && data.moduleCode !== context.moduleCode)) throw new Error('返回的任务视图与当前选择不一致')
  if (!Array.isArray(data.allowedVisibilities) || !data.allowedVisibilities.includes(context.visibility)
    || data.allowedVisibilities.some(value => !['OWN', 'MODULE', 'TENANT'].includes(value)) || !Array.isArray(data.allowedModules)) throw new Error('未取得任务视图授权，请重新读取')
}
function pageResult(data, page, pageSize) {
  if (!data || !Array.isArray(data.list) || !number(data.total) || data.page !== page || data.pageSize !== pageSize || data.list.length > pageSize || data.total < data.list.length) throw new Error('任务分页不完整，不能把当前页当作全部记录')
  return data
}
export function createExchangeState(initialVisibility = 'OWN') {
  return {
    view: { visibility: initialVisibility, moduleCode: '' }, access: null,
    filters: { keyword: '', jobType: '', status: '' }, applied: { keyword: '', jobType: '', status: '' },
    list: { rows: [], total: null, page: 1, pageSize: 20, loading: false, error: '' },
    summary: { data: null, loading: false, error: '' },
    detail: { ref: null, item: null, loading: false, error: '' },
    errors: { rows: [], total: null, page: 1, pageSize: 20, loading: false, error: '' },
    pending: null, busy: false, receipt: '', operationError: '', unresolved: {}
  }
}
const errorText = error => String(error?.message || '请求结果未取得，请重新读取').replace(/([?&](?:ticket|token)=)[^\s&]+/gi, '$1[已隐藏]')

/** One controller per actor/tenant context. Never retries a business write automatically. */
export function createExchangeController({ state, api, rights }) {
  let alive = true, generation = 0
  const channels = new Map()
  const fence = channel => {
    const serial = (channels.get(channel) || 0) + 1, stamp = generation
    channels.set(channel, serial)
    return () => alive && stamp === generation && channels.get(channel) === serial
  }
  const context = () => ({ ...state.view })
  const readTask = (ref, view) => ref.jobType === 'IMPORT' ? api.getImport(ref.id, view) : api.getExport(ref.id, view)
  const clearDetail = () => {
    fence('detail'); fence('errors')
    state.detail = { ref: null, item: null, loading: false, error: '' }
    state.errors = { rows: [], total: null, page: 1, pageSize: 20, loading: false, error: '' }
  }
  const acceptAccess = data => { state.access = { allowedVisibilities: [...data.allowedVisibilities], allowedModules: [...data.allowedModules] } }
  const patchRow = row => {
    const i = state.list.rows.findIndex(item => taskKey(item) === taskKey(row))
    if (i >= 0) state.list.rows.splice(i, 1, row)
    if (state.detail.ref && taskKey(state.detail.ref) === taskKey(row)) state.detail.item = row
  }
  const controller = {
    dispose() { alive = false; generation += 1; channels.clear() },
    async loadList(page = state.list.page) {
      if (!alive || state.busy || !rights().read || !Number.isInteger(page) || page < 1) return false
      const current = fence('list'), view = context(), pageSize = state.list.pageSize
      state.list.loading = true; state.list.error = ''; state.list.rows = []; state.list.total = null
      try {
        const data = await api.list({ ...state.applied, ...view, page, pageSize })
        if (!current()) return false
        responseContext(data, view); pageResult(data, page, pageSize)
        const keys = new Set()
        for (const row of data.list) { assertTask(row); if (keys.has(taskKey(row))) throw new Error('任务目录存在重复编号'); keys.add(taskKey(row)) }
        acceptAccess(data); state.list = { rows: data.list, total: data.total, page, pageSize, loading: false, error: '' }
        return true
      } catch (error) { if (current()) state.list.error = errorText(error); return false }
      finally { if (current()) state.list.loading = false }
    },
    async loadSummary() {
      if (!alive || state.busy || !rights().read) return false
      const current = fence('summary'), view = context()
      state.summary = { data: null, loading: true, error: '' }
      try {
        const data = await api.summary(view)
        if (!current()) return false
        responseContext(data, view); acceptAccess(data)
        const values = Object.fromEntries(['total', 'imports', 'exports', 'pending', 'scanning', 'failed', 'expired', 'receipts'].map(key => [key, number(data[key]) ? data[key] : null]))
        state.summary.data = { ...values, generatedAt: data.generatedAt || null }; return true
      } catch (error) { if (current()) state.summary.error = errorText(error); return false }
      finally { if (current()) state.summary.loading = false }
    },
    async refresh() { if (state.busy) return; await Promise.all([controller.loadList(), controller.loadSummary()]) },
    async search() {
      if (!alive || state.busy || state.pending) return
      state.applied = { ...state.filters, keyword: state.filters.keyword.trim() }
      await controller.loadList(1)
    },
    async changeView(visibility, moduleCode = '') {
      if (!alive || state.busy || state.pending || !state.access?.allowedVisibilities.includes(visibility)
        || (visibility === 'MODULE' && !state.access.allowedModules.includes(moduleCode))) return false
      generation += 1; channels.clear(); clearDetail(); state.receipt = ''; state.operationError = ''
      state.view = { visibility, moduleCode: visibility === 'MODULE' ? moduleCode : '' }
      state.list.page = 1
      await controller.refresh(); return true
    },
    async openDetail(rawRef) {
      if (!alive || state.busy || !rights().read || state.pending) return false
      const current = fence('detail'), view = context()
      fence('errors'); state.errors = { rows: [], total: null, page: 1, pageSize: 20, loading: false, error: '' }
      state.detail = { ref: null, item: null, loading: true, error: '' }
      try {
        const ref = taskRef(rawRef); state.detail.ref = ref
        const item = await readTask(ref, view)
        if (!current()) return false
        assertTask(item, ref); state.detail.item = item; patchRow(item)
        const pending = state.unresolved[taskKey(item)]
        if (pending && item.version > pending.version) {
          delete state.unresolved[taskKey(item)]
          state.receipt = `已重新读取任务 #${item.id}，当前为「${taskStatus(item)}」，版本 ${item.version}。没有重放上次操作。`
        }
        return true
      } catch (error) { if (current()) state.detail.error = errorText(error); return false }
      finally { if (current()) state.detail.loading = false }
    },
    closeDetail() { if (!state.busy && !state.pending) clearDetail() },
    async loadErrors(page = 1) {
      const ref = state.detail.ref
      if (!alive || !rights().read || state.detail.loading || !state.detail.item || ref?.jobType !== 'IMPORT' || !Number.isInteger(page) || page < 1) return
      const current = fence('errors'), key = taskKey(ref), view = context(), pageSize = state.errors.pageSize
      state.errors = { rows: [], total: null, page, pageSize, loading: true, error: '' }
      try {
        const data = await api.getImportErrors(ref.id, { ...view, page, pageSize })
        if (!current() || !state.detail.ref || taskKey(state.detail.ref) !== key) return
        pageResult(data, page, pageSize)
        state.errors = { rows: data.list.map(row => ({ id: row.id, rowNo: row.rowNo, sheetName: row.sheetName, fieldCode: row.fieldCode, errorCode: row.errorCode, message: row.message })), total: data.total, page, pageSize, loading: false, error: '' }
      } catch (error) { if (current()) state.errors.error = errorText(error) }
      finally { if (current()) state.errors.loading = false }
    },
    async prepare(type, row) {
      if (!alive || state.busy || state.pending || state.unresolved[taskKey(row)] || !actionAvailable(type, row, rights())) return
      const current = fence('action'), ref = taskRef(row), view = context()
      state.busy = true; state.operationError = ''; state.receipt = ''
      try {
        const fresh = await readTask(ref, view)
        if (!current()) return
        assertTask(fresh, ref); patchRow(fresh)
        if (!actionAvailable(type, fresh, rights())) throw new Error('任务状态或操作权限已经变化，请按最新结果办理')
        state.pending = { type, row: fresh, fingerprint: taskFingerprint(fresh), reason: '', acknowledged: false }
      } catch (error) { if (current()) state.operationError = errorText(error) }
      finally { if (current()) state.busy = false }
    },
    closeAction() { if (!state.busy) state.pending = null },
    async perform() {
      const p = state.pending
      if (!alive || !p || state.busy || !p.acknowledged || !actionAvailable(p.type, p.row, rights()) || state.unresolved[taskKey(p.row)]) return
      const reason = p.reason.trim()
      if (['cancel', 'revoke'].includes(p.type) && (reason.length < 5 || reason.length > 500)) { state.operationError = '请填写 5—500 个字符的业务原因'; return }
      const current = fence('action'), ref = taskRef(p.row), view = context(), key = taskKey(ref)
      state.busy = true; state.operationError = ''; state.receipt = ''
      let submitted = false
      try {
        const fresh = await readTask(ref, view)
        if (!current()) return
        assertTask(fresh, ref)
        if (taskFingerprint(fresh) !== p.fingerprint || !actionAvailable(p.type, fresh, rights())) {
          patchRow(fresh); state.pending = null
          throw new Error('任务状态、版本或权限已变化，本次没有提交。请重新核对。')
        }
        submitted = true
        if (p.type === 'confirm') await api.confirmImport(ref.id, fresh.version)
        else if (p.type === 'retry') await api.retryImport(ref.id, fresh.version)
        else if (p.type === 'cancel') await api.cancelImport(ref.id, fresh.version, reason)
        else if (p.type === 'revoke') await api.revokeExport(ref.id, fresh.version, reason)
        else if (p.type === 'download') await api.downloadExport(fresh) // Never put the returned ticket into component state.
        if (!current()) return
        state.pending = null
        const saved = await readTask(ref, view)
        if (!current()) return
        assertTask(saved, ref); patchRow(saved)
        if (saved.version <= fresh.version) throw new Error('请求已返回，但尚未读取到新版本，请继续核对，勿重复操作')
        delete state.unresolved[key]
        state.receipt = p.type === 'download'
          ? `已将文件交给浏览器下载，并回读任务版本 ${saved.version}。请核对浏览器下载结果；票据未保存在页面。`
          : `已重新读取任务 #${saved.id}：${taskStatus(saved)} · 版本 ${saved.version}。`
      } catch (error) {
        if (!current()) return
        state.operationError = errorText(error)
        if (submitted) { state.unresolved[key] = { type: p.type, version: p.row.version }; state.pending = null; state.receipt = '本次操作结果需要核对。已阻止重复请求，请重新读取任务状态。' }
      } finally { if (current()) state.busy = false }
      if (current()) await Promise.all([controller.loadList(), controller.loadSummary()])
    }
  }
  return controller
}
