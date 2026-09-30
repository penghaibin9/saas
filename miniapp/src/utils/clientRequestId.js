const SEQUENCE_KEY = 'student_lifecycle_client_request_sequence'
let memorySequence = 0

function nextSequence() {
  memorySequence += 1
  try {
    const stored = Number(uni.getStorageSync(SEQUENCE_KEY) || 0)
    memorySequence = Math.max(memorySequence, stored + 1)
    uni.setStorageSync(SEQUENCE_KEY, memorySequence)
  } catch (_) {
    // Storage may be unavailable during very early bootstrap; the in-memory
    // sequence still prevents same-millisecond collisions in this process.
  }
  return memorySequence
}

/**
 * A stable business request id generator shared by H5 and mp-weixin.
 * Call once per user intent and keep the returned value for every retry.
 */
export function createClientRequestId(prefix = 'request') {
  let suffix = ''
  try {
    suffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : ''
  } catch (_) {}
  if (!suffix) {
    suffix = `${Date.now().toString(36)}-${nextSequence().toString(36)}`
  }
  return `${String(prefix || 'request')}-${suffix}`.slice(0, 100)
}

export default createClientRequestId
