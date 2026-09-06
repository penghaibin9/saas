import { canConfirmIdentityImport, isIdentityImportProcessing } from './identityImportState.js'

// Presentation and request lifecycle only. The existing Data Exchange API owns all writes.
export const IMPORT_TYPES = { teachers: 'IDENTITY_TEACHER', students: 'IDENTITY_STUDENT' }
const COUNT_STATES = new Set(['VALIDATED', 'VALIDATION_FAILED', 'CONFIRMING', 'SUCCEEDED'])
const LABELS = {
  SCANNING: '安全扫描中', WORKER_CLAIMED: '后台已领取', PARSING: '服务端预检中',
  VALIDATED: '预检通过 · 尚未导入', VALIDATION_FAILED: '预检未通过',
  CONFIRMING: '正在确认导入', SUCCEEDED: '导入已完成', FAILED: '处理失败',
  CANCELLED: '任务已取消', EXPIRED: '任务已过期'
}
const validNumber = value => Number.isSafeInteger(value) && value >= 0
export const importStatusLabel = job => LABELS[job?.status] || '状态待核对'
export const countText = value => validNumber(value) ? String(value) : '未取得'
export const validJobId = value => typeof value === 'string' && /^[1-9]\d*$/.test(value)

export function identityJob(job, kind, id = '') {
  if (!IMPORT_TYPES[kind] || !job || !validJobId(String(job.id || ''))
    || (id && String(job.id) !== String(id)) || job.jobType !== 'IMPORT'
    || job.importType !== IMPORT_TYPES[kind] || job.moduleCode !== 'SYSTEM'
    || typeof job.status !== 'string' || !validNumber(job.version)) {
    throw new Error('任务编号、身份类型或版本不匹配，请从对应的师生导入入口重新读取')
  }
  return job
}

export function importCounts(job) {
  const ready = COUNT_STATES.has(job?.status)
  return Object.fromEntries(['totalRows', 'validRows', 'invalidRows'].map(key =>
    [key, ready && validNumber(job?.[key]) ? job[key] : null]))
}

export function confirmableJob(job) {
  const counts = importCounts(job)
  return canConfirmIdentityImport(job) && validNumber(job?.version)
    && Object.values(counts).every(validNumber)
    && counts.invalidRows === 0 && counts.validRows > 0
    && counts.totalRows === counts.validRows + counts.invalidRows
}

export function reviewFingerprint(job) {
  return JSON.stringify([String(job.id), job.importType, job.status, job.version,
    job.sourceFileId || '', job.totalRows, job.validRows, job.invalidRows])
}

export function importReceiptCounts(job, kind) {
  if (job?.status !== 'SUCCEEDED') return []
  const entities = job.result?.entities || {}, summary = job.result?.summary || {}
  const rows = kind === 'students'
    ? [['新建学生主档', entities.students?.created], ['复用已有主档', summary.studentsReused],
      ['新建学生账号', entities.studentAccounts?.created], ['已存在跳过', summary.accountsSkipped]]
    : [['新建教职工', entities.teachers?.created], ['已确认行数', job.confirmedRows]]
  return rows.map(([label, value]) => ({ label, value: validNumber(value) ? value : null }))
}

export function createImportState() {
  return { file: null, job: null, busy: '', error: '', note: '', review: null,
    acknowledged: false, uncertain: false, uploadUncertain: false, readback: false,
    errors: { rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '' } }
}

/** Scoped controller: one identity kind, one UI context, no timers/writes after disposal. */
export function createImportController({ state, api, kind, canUpload, canConfirm, onJobId = () => {} }) {
  if (!IMPORT_TYPES[kind]) throw new Error('不支持的身份导入类型')
  let epoch = 0, alive = true, abort = null, errorEpoch = 0
  const begin = () => {
    abort?.abort(); abort = new AbortController()
    const stamp = ++epoch
    return () => alive && stamp === epoch
  }
  const clearErrors = () => {
    errorEpoch += 1
    state.errors = { rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '' }
  }
  const apply = job => { state.job = job; state.review = null; state.acknowledged = false }
  const message = error => error?.message || '请求结果未取得，请重新读取任务状态'
  const finish = async current => {
    if (!current()) return
    if (state.job.status === 'SUCCEEDED') { state.readback = true; state.uncertain = false }
    if (state.job.status === 'VALIDATION_FAILED' || state.job.invalidRows > 0) await controller.loadErrors(1)
  }
  const poll = async current => {
    if (!current() || !isIdentityImportProcessing(state.job)) return
    state.busy = 'poll'
    const jobId = String(state.job.id)
    const job = await api.waitIdentityValidation(jobId, { signal: abort.signal })
    if (!current()) return
    apply(identityJob(job, kind, jobId))
    if (job.pollTimedOut) state.note = '名单仍在后台处理；可稍后重新读取，不需要重新上传。'
  }
  const controller = {
    dispose() { alive = false; epoch += 1; errorEpoch += 1; abort?.abort() },
    selectFile(file) {
      if (!alive || state.busy || state.job) return false
      if (!file || !/\.xlsx$/i.test(file.name || '') || !(file.size > 0)) {
        state.error = '请选择非空的标准 .xlsx 文件'; state.file = null; return false
      }
      state.file = file; state.uploadUncertain = false; state.error = ''; state.note = ''; return true
    },
    async upload() {
      if (!alive || !canUpload() || state.busy || !state.file || state.job) return
      const current = begin(); state.busy = 'upload'; state.error = ''; state.note = ''
      try {
        // The API's WeakMap retains the same upload key for this exact File object on explicit retry.
        const created = await api.validateIdentity(kind, state.file)
        if (!current()) return
        apply(identityJob(created, kind)); state.uploadUncertain = false; state.readback = false
        onJobId(String(created.id))
        if (isIdentityImportProcessing(created)) await poll(current)
        else {
          const stored = await api.getImport(String(created.id))
          if (!current()) return
          apply(identityJob(stored, kind, String(created.id)))
        }
        await finish(current)
      } catch (error) {
        if (current() && error?.name !== 'AbortError') {
          state.error = message(error); state.uploadUncertain = !state.job
          state.note = state.job ? '任务已登记。重新读取状态，不要再次上传相同名单。'
            : '上传结果未取得；重试会保留当前文件和同一次上传标识。'
        }
      } finally { if (current()) state.busy = '' }
    },
    async resume(jobId) {
      if (!alive || state.busy) return
      if (!validJobId(String(jobId || ''))) { state.error = '任务编号无效'; return }
      const current = begin(); state.busy = 'read'; state.error = ''; state.note = ''
      state.review = null; state.acknowledged = false; state.readback = false
      clearErrors()
      if (String(state.job?.id || '') !== String(jobId)) { state.job = null; state.file = null; state.uncertain = false }
      try {
        const job = await api.getImport(jobId)
        if (!current()) return
        apply(identityJob(job, kind, jobId)); await poll(current); await finish(current)
      } catch (error) {
        if (current() && error?.name !== 'AbortError') state.error = message(error)
      } finally { if (current()) state.busy = '' }
    },
    async prepareReview() {
      if (!alive || !canConfirm() || state.busy || state.uncertain || !confirmableJob(state.job)) return
      const current = begin(), jobId = String(state.job.id)
      state.busy = 'review'; state.error = ''; state.review = null; state.acknowledged = false
      try {
        const job = identityJob(await api.getImport(jobId), kind, jobId)
        if (!current()) return
        apply(job)
        if (!confirmableJob(job)) { state.note = '服务端预检状态已变化，请按最新结果处理。'; await finish(current); return }
        state.review = reviewFingerprint(job); state.note = ''
      } catch (error) { if (current()) state.error = message(error) }
      finally { if (current()) state.busy = '' }
    },
    cancelReview() { if (!state.busy) { state.review = null; state.acknowledged = false } },
    async confirm() {
      if (!alive || !canConfirm() || state.busy || state.uncertain || !state.acknowledged
        || !state.review || !confirmableJob(state.job)) return
      const currentRequest = begin(), jobId = String(state.job.id), approved = state.review
      state.busy = 'confirm'; state.error = ''; state.note = ''; state.readback = false
      let submitted = false
      try {
        const current = await api.getImport(jobId)
        if (!currentRequest()) return
        identityJob(current, kind, jobId)
        if (!canConfirmIdentityImport(current) || !confirmableJob(current)
          || reviewFingerprint(current) !== approved) {
          apply(current); state.note = '任务状态、版本或数量已变化，本次未提交。请重新核对。'; return
        }
        if (!canConfirm()) { state.error = '当前身份已无确认权限，请重新取得学校上下文'; return }
        submitted = true
        const result = await api.confirmImport(jobId, current.version)
        if (!currentRequest()) return
        apply(identityJob(result, kind, jobId)); state.uncertain = true
        state.note = '确认请求已返回，正在重新读取最终任务状态。'
        const saved = await api.getImport(jobId)
        if (!currentRequest()) return
        apply(identityJob(saved, kind, jobId)); await finish(currentRequest)
        state.note = state.readback ? '已从服务端重新读取完成结果。初始凭据仅在任务中心受控下载。'
          : '确认请求已受理，最终状态仍需核对。请重新读取，不要再次确认。'
      } catch (error) {
        if (!currentRequest()) return
        state.error = message(error); state.review = null; state.acknowledged = false
        if (submitted) {
          state.uncertain = true
          state.note = '确认结果不确定，已阻止重复写入。请重新读取任务状态。'
        }
      } finally { if (currentRequest()) state.busy = '' }
    },
    async loadErrors(page = 1) {
      if (!alive || !state.job || !Number.isInteger(page) || page < 1) return
      const jobId = String(state.job.id), stamp = ++errorEpoch
      const current = () => alive && stamp === errorEpoch && String(state.job?.id) === jobId
      state.errors.loading = true; state.errors.error = ''; state.errors.rows = []
      try {
        const data = await api.getImportErrors(jobId, { page, pageSize: state.errors.pageSize })
        if (!current()) return
        if (!data || !Array.isArray(data.list) || !validNumber(data.total)
          || data.page !== page || !Number.isSafeInteger(data.pageSize) || data.pageSize < 1) {
          throw new Error('错误明细分页不完整，不能显示为空记录')
        }
        // Never render or export raw_snapshot_json (identity documents or credentials).
        state.errors = { rows: data.list.map(row => ({ id: row.id, rowNo: row.rowNo,
          sheetName: row.sheetName, fieldCode: row.fieldCode, errorCode: row.errorCode, message: row.message })),
        total: data.total, page: data.page, pageSize: data.pageSize, loading: false, error: '' }
      } catch (error) { if (current()) state.errors.error = message(error) }
      finally { if (current()) state.errors.loading = false }
    }
  }
  return controller
}
