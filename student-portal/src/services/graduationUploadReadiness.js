const SAFE_SCAN_STATES = new Set(['CLEAN', 'NOT_REQUIRED'])
const BLOCKED_SCAN_STATES = new Set(['INFECTED', 'ERROR', 'REJECTED', 'QUARANTINED'])

export function graduationUploadReady(file) {
  return Boolean(file?.fileId && file.readyForBusiness === true
    && SAFE_SCAN_STATES.has(String(file.scanStatus || '').toUpperCase()))
}

export function graduationUploadPhase(file) {
  if (!file?.fileId) return 'idle'
  if (BLOCKED_SCAN_STATES.has(String(file.scanStatus || '').toUpperCase())) return 'blocked'
  return graduationUploadReady(file) ? 'ready' : 'waiting'
}

function cancelledError() {
  const error = new Error('文件检查已停止')
  error.name = 'AbortError'
  return error
}

/** Read only the uploaded file; never replace it with a different server object. */
export async function readGraduationUpload(file, readMetadata, { timeoutMs = 10_000, signal } = {}) {
  const expected = { ...file }
  const fileId = String(expected.fileId || '')
  if (!fileId) throw new Error('请先上传文件')
  if (typeof readMetadata !== 'function') throw new TypeError('readMetadata is required')
  if (signal?.aborted) throw cancelledError()

  const metadata = await new Promise((resolve, reject) => {
    let settled = false
    let timer
    const finish = (fn, value) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
      fn(value)
    }
    const abort = () => finish(reject, cancelledError())
    signal?.addEventListener('abort', abort, { once: true })
    timer = setTimeout(() => finish(reject, new Error('获取文件状态超时，请重新检查，无需重复上传')), timeoutMs)
    // Transport may have its own timeout. The local deadline and cancellation
    // still settle this reader and ignore any late transport result.
    Promise.resolve().then(() => readMetadata(fileId, { signal }))
      .then((value) => finish(resolve, value), (error) => finish(reject, error))
  })

  if (!metadata || String(metadata.fileId || '') !== fileId) {
    throw new Error('文件身份不一致，已停止本次检查，请重新选择文件')
  }
  for (const field of ['fileVersionId', 'sha256']) {
    if (expected[field] != null && metadata[field] != null
      && String(expected[field]) !== String(metadata[field])) {
      throw new Error('文件版本发生变化，已停止本次检查，请重新选择文件')
    }
  }
  const allowedActions = Array.isArray(metadata.allowedActions) ? [...metadata.allowedActions] : []
  const next = {
    ...expected,
    ...metadata,
    fileId: expected.fileId,
    allowedActions,
    readyForBusiness: graduationUploadReady(metadata),
    canPreview: false,
    canDownload: false
  }
  // A previous upload response must not contribute stale permissions.
  next.canPreview = next.readyForBusiness && allowedActions.includes('preview')
  next.canDownload = next.readyForBusiness && allowedActions.includes('download')
  return next
}

/**
 * Bounded, single-flight readback for one pending upload. It never submits,
 * rescans, changes a business version or upgrades a server rejection.
 */
export function createGraduationUploadMonitor({
  readMetadata,
  onFile = () => {},
  onState = () => {},
  intervalMs = 2_000,
  maxWaitMs = 60_000,
  requestTimeoutMs = 10_000,
  now = () => Date.now()
}) {
  if (typeof readMetadata !== 'function') throw new TypeError('readMetadata is required')
  let generation = 0
  let timer = null
  let controller = null
  let inFlight = null
  let current = null
  let deadline = 0

  function stop() {
    generation += 1
    clearTimeout(timer)
    timer = null
    controller?.abort()
    controller = null
    inFlight = null
  }

  function state(phase, message) {
    onState({ phase, message, fileId: String(current?.fileId || '') })
  }

  function unavailable(phase, message) {
    current = { ...current, readyForBusiness: false, canPreview: false, canDownload: false, allowedActions: [] }
    onFile(current)
    state(phase, message)
  }

  async function check(token) {
    if (token !== generation || !current?.fileId) return
    const remaining = deadline - now()
    if (remaining <= 0) {
      unavailable('timeout', '安全检查尚未完成，可重新检查状态，无需重复上传。')
      return
    }
    state('checking', '正在获取文件安全检查结果…')
    const requestController = new AbortController()
    controller = requestController
    try {
      const fresh = await readGraduationUpload(current, readMetadata, {
        signal: requestController.signal,
        timeoutMs: Math.max(1, Math.min(requestTimeoutMs, remaining))
      })
      if (token !== generation) return
      current = fresh
      onFile(fresh)
      const phase = graduationUploadPhase(fresh)
      if (phase === 'ready') {
        state('ready', '安全检查已通过，确认文件后即可提交。')
      } else if (phase === 'blocked') {
        state('blocked', fresh.statusText || '文件未通过安全检查，请检查文件或联系学校。')
      } else if (now() >= deadline) {
        unavailable('timeout', '安全检查尚未完成，可重新检查状态，无需重复上传。')
      } else {
        state('waiting', '文件已上传，正在等待安全检查；通过后即可提交。')
        timer = setTimeout(() => {
          timer = null
          inFlight = check(token)
        }, Math.min(intervalMs, Math.max(1, deadline - now())))
      }
    } catch (error) {
      if (token !== generation || error?.name === 'AbortError') return
      unavailable('error', '暂时无法确认文件状态，请重新检查；无需重复上传。')
    } finally {
      if (token === generation) {
        controller = null
        inFlight = null
      }
    }
  }

  function start(file, { force = false } = {}) {
    stop()
    current = file?.fileId ? { ...file } : null
    deadline = now() + maxWaitMs
    const phase = graduationUploadPhase(current)
    if (phase === 'idle') {
      state('idle', '')
      return Promise.resolve()
    }
    if (!force && phase === 'ready') {
      state('ready', '安全检查已通过，确认文件后即可提交。')
      return Promise.resolve()
    }
    if (!force && phase === 'blocked') {
      unavailable('blocked', current.statusText || '文件未通过安全检查，请检查文件或联系学校。')
      return Promise.resolve()
    }
    // Explicitly fail closed while checking; never infer readiness from time.
    unavailable('waiting', '文件已上传，正在等待安全检查；通过后即可提交。')
    inFlight = check(generation)
    return inFlight
  }

  function recheck() {
    if (inFlight) return inFlight
    return start(current, { force: true })
  }

  return { start, recheck, stop }
}
