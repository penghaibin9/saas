import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import {
  PREVIEW_KIND,
  PREVIEW_SESSION_STATE,
  isTicketExpiredError,
  normalizePreviewDescriptor,
  normalizePreviewError,
  previewIdentity,
  previewSourceByteLimit
} from './viewer-contract'

function sourceByteLength(value) {
  if (value instanceof Blob) return Number(value.size || 0)
  if (value instanceof ArrayBuffer) return value.byteLength
  if (ArrayBuffer.isView(value)) return value.byteLength
  return 0
}

function tooLargeError(descriptor, limit) {
  const label = descriptor.previewKind === PREVIEW_KIND.DOCX
    ? 'DOCX'
    : descriptor.previewKind === PREVIEW_KIND.PDF ? 'PDF' : '图片'
  const mb = Math.max(1, Math.floor(limit / (1024 * 1024)))
  const error = new Error(`${label} 超过 ${mb}MB 站内阅读上限，请下载原文查看`)
  error.code = 'PREVIEW_TOO_LARGE'
  error.retryable = false
  return error
}

export function usePreviewSession(provider) {
  const state = reactive({
    status: PREVIEW_SESSION_STATE.IDLE,
    generation: 0,
    identity: '',
    descriptor: null,
    error: null,
    ticketRefreshCount: 0
  })
  const source = ref(null)
  let controller = null

  const ready = computed(() => state.status === PREVIEW_SESSION_STATE.READY)

  function releaseSource() {
    source.value = null
  }

  function cancelActive() {
    controller?.abort()
    controller = null
  }

  async function load(rawDescriptor) {
    const descriptor = rawDescriptor ? normalizePreviewDescriptor(rawDescriptor) : null
    const generation = state.generation + 1
    state.generation = generation
    cancelActive()
    releaseSource()
    state.error = null
    state.ticketRefreshCount = 0
    state.descriptor = descriptor
    state.identity = descriptor ? previewIdentity(descriptor) : ''

    if (!descriptor) {
      state.status = PREVIEW_SESSION_STATE.IDLE
      return
    }
    if (!descriptor.canPreview) {
      state.status = PREVIEW_SESSION_STATE.ERROR
      state.error = { code: 'NO_PERMISSION', message: '当前文件没有预览权限', retryable: false }
      return
    }
    const sourceLimit = previewSourceByteLimit(descriptor)
    if (sourceLimit && Number(descriptor.sizeBytes || 0) > sourceLimit) {
      state.status = PREVIEW_SESSION_STATE.ERROR
      state.error = normalizePreviewError(tooLargeError(descriptor, sourceLimit))
      return
    }
    if (descriptor.previewKind === PREVIEW_KIND.UNSUPPORTED) {
      state.status = PREVIEW_SESSION_STATE.UNSUPPORTED
      return
    }
    if (!provider || typeof provider.fetchBytes !== 'function') {
      state.status = PREVIEW_SESSION_STATE.ERROR
      state.error = { code: 'PREVIEW_PROVIDER_MISSING', message: '预览服务未配置', retryable: false }
      return
    }

    controller = new AbortController()
    state.status = PREVIEW_SESSION_STATE.FETCHING
    try {
      let bytes
      try {
        bytes = await provider.fetchBytes(descriptor, { signal: controller.signal, refresh: false })
      } catch (error) {
        if (!isTicketExpiredError(error)) throw error
        state.ticketRefreshCount = 1
        bytes = await provider.fetchBytes(descriptor, { signal: controller.signal, refresh: true })
      }
      if (generation !== state.generation || controller.signal.aborted) return
      if (sourceLimit && sourceByteLength(bytes) > sourceLimit) throw tooLargeError(descriptor, sourceLimit)
      source.value = bytes
      state.status = PREVIEW_SESSION_STATE.READY
    } catch (error) {
      if (generation !== state.generation || error?.name === 'AbortError') return
      state.status = PREVIEW_SESSION_STATE.ERROR
      state.error = normalizePreviewError(error)
    }
  }

  function retry() {
    if (state.descriptor) return load(state.descriptor)
  }

  function destroy() {
    state.generation += 1
    cancelActive()
    releaseSource()
    state.status = PREVIEW_SESSION_STATE.DESTROYED
    try { provider?.dispose?.() } catch { /* presentation cleanup must not break page teardown */ }
  }

  onBeforeUnmount(destroy)
  return { state, source, ready, load, retry, destroy }
}
