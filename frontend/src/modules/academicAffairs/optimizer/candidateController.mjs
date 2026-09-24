/** Candidate-only controller. Dependencies injected for tests; no tokens are persisted. */
export function stableJSON(value) {
  if (Array.isArray(value)) return '[' + value.map(stableJSON).join(',') + ']'
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort()
    .map(key => JSON.stringify(key) + ':' + stableJSON(value[key])).join(',') + '}'
  return JSON.stringify(value)
}
export async function sha256(text) {
  if (!globalThis.crypto?.subtle) throw new Error('SECURE_DIGEST_UNAVAILABLE')
  const hash = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return [...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, '0')).join('')
}
const terminal = new Set(['SUCCEEDED','INFEASIBLE','UNKNOWN','REJECTED','STALE','CANCELLED','FAILED','APPLIED'])
const validId = value => typeof value === 'string' && /^[1-9][0-9]{0,18}$/.test(value)
export function createCandidateController({ api, readIdentity, storage, state = {}, digest = sha256,
  randomId = () => globalThis.crypto.randomUUID() }) {
  let generation = 0, batch = '', identity = '', epochs = {}, pending = null, disposed = false
  Object.assign(state, { context: null, job: null, rows: [], error: '', busy: false, storageBlocked: false, unknown: false })
  const key = () => 'yueke-schedule-candidate:' + encodeURIComponent(identity) + ':' + batch
  const live = () => !disposed && identity && readIdentity() === identity && validId(batch)
  const begin = channel => {
    const g = generation, n = epochs[channel] = (epochs[channel] || 0) + 1
    return () => live() && g === generation && epochs[channel] === n
  }
  function save(record) {
    if (!live()) throw new Error('IDENTITY_CHANGED')
    try { storage.setItem(key(), JSON.stringify(record)); pending = record }
    catch { state.storageBlocked = true; throw new Error('COMMAND_STORAGE_UNAVAILABLE') }
  }
  function accept(job) {
    if (!job || !validId(job.jobId) || job.batchId !== batch || !Number.isSafeInteger(job.version)) {
      throw new Error('INVALID_JOB_RECEIPT')
    }
    state.job = job; state.unknown = false
    if (pending) save({ ...pending, jobId: job.jobId, state: terminal.has(job.state) ? 'TERMINAL' : 'ACK' })
    return job
  }
  function fail(error) {
    state.error = error?.message || 'REQUEST_FAILED'
    if ([401,403,404].includes(error?.httpStatus || error?.status)) {
      state.context = null; state.job = null; state.rows = []; state.application = null
    }
  }
  const controller = {
    state,
    setScope(nextBatch) {
      generation++; epochs = {}; batch = String(nextBatch || ''); identity = readIdentity() || ''; pending = null
      Object.assign(state, { context: null, job: null, rows: [], application: null, error: '', busy: false, unknown: false, storageBlocked: false })
      if (!live()) return
      try {
        const saved = JSON.parse(storage.getItem(key()) || 'null')
        if (saved && saved.identity === identity && saved.batchId === batch && typeof saved.idempotencyKey === 'string') {
          pending = saved; state.unknown = saved.state !== 'TERMINAL'
        }
      } catch { state.storageBlocked = true }
    },
    async load() {
      if (!live()) return null
      const valid = begin('context'); state.error = ''; state.context = null
      try { const result = await api.context(batch); if (valid()) state.context = result; return valid() ? result : null }
      catch (error) { if (valid()) fail(error); return null }
    },
    async submit(body) {
      if (!live() || state.busy || state.storageBlocked || !state.context?.canGenerate) return null
      const valid = begin('write'); state.busy = true; state.error = ''
      const targetBatch = batch
      try {
        const immutableBody = JSON.parse(stableJSON(body))
        const signature = await digest(stableJSON(immutableBody))
        if (!valid()) return null
        if (pending && pending.state !== 'TERMINAL' && pending.signature !== signature) {
          throw new Error('UNRESOLVED_COMMAND_CHANGED_INPUT')
        }
        const reuse = pending && pending.state !== 'TERMINAL'
        const record = reuse ? pending : { identity, batchId: batch, signature, idempotencyKey: randomId(), state: 'UNKNOWN' }
        save(record); state.unknown = true
        const job = await api.enqueue(targetBatch, { ...immutableBody, idempotencyKey: record.idempotencyKey })
        if (!valid()) return null
        return accept(job)
      } catch (error) { if (valid()) fail(error); return null }
      finally { if (valid()) state.busy = false }
    },
    async recover() {
      if (!live() || !pending) return null
      const valid = begin('job')
      try {
        const result = await api.lookup(batch, pending.idempotencyKey)
        if (!valid()) return null
        if (result?.found) return accept(result.job)
        state.unknown = true; state.error = 'RESULT_NOT_CONFIRMED_RETRY_SAME_COMMAND_ONLY'
      } catch (error) { if (valid()) fail(error) }
      return null
    },
    async refresh() {
      if (!live()) return null
      const jobId = state.job?.jobId || pending?.jobId
      if (!jobId) return controller.recover()
      const valid = begin('job')
      try { const job = await api.get(batch, jobId); return valid() ? accept(job) : null }
      catch (error) { if (valid()) fail(error); return null }
    },
    async cancel() {
      if (!live() || state.busy || !state.job || terminal.has(state.job.state)) return null
      const valid = begin('write'), job = { ...state.job }; state.busy = true
      try { const result = await api.cancel(batch, job.jobId, job.version); return valid() ? accept(result) : null }
      catch (error) { if (valid()) { fail(error); state.unknown = true }; return null }
      finally { if (valid()) state.busy = false }
    },
    async preview(taskId, week) {
      if (!live() || !state.job || state.job.state !== 'SUCCEEDED') return null
      const valid = begin('preview'), jobId = state.job.jobId; state.rows = []
      try {
        const result = await api.preview(batch, jobId, taskId, week)
        if (!valid()) return null
        if (result?.truncated) throw new Error('PREVIEW_FILTER_REQUIRED')
        state.rows = result.rows || []; return result
      } catch (error) { if (valid()) fail(error); return null }
    },
    async apply() {
      if (!live() || state.busy || !state.job?.canApply) return null
      const valid = begin('write'), job = { ...state.job }
      state.busy = true; state.error = ''
      try {
        const receipt = await api.apply(batch, job.jobId, job.version)
        if (!valid()) return null
        state.application = receipt
        await controller.refresh()
        return valid() ? receipt : null
      } catch (error) { if (valid()) fail(error); return null }
      finally { if (valid()) state.busy = false }
    },
    isTerminal() { return !!state.job && terminal.has(state.job.state) },
    dispose() { disposed = true; generation++; state.context = null; state.job = null; state.rows = []; state.application = null; state.busy = false }
  }
  return controller
}
