import { onBeforeUnmount, ref } from 'vue'

function identity(file = {}) {
  return [file.fileId || '', file.fileVersionId || file.versionId || '', file.sourceSha256 || file.sha256 || ''].join(':')
}

export function useStudentPreviewSession(loadPreview) {
  const status = ref('idle')
  const objectUrl = ref('')
  const error = ref('')
  const mimeType = ref('')
  const activeIdentity = ref('')
  let controller = null
  let generation = 0

  function release() {
    controller?.abort()
    controller = null
    if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = ''
    mimeType.value = ''
  }

  async function open(file) {
    generation += 1
    const currentGeneration = generation
    release()
    error.value = ''
    activeIdentity.value = identity(file)
    if (!file?.fileId || typeof loadPreview !== 'function') {
      status.value = 'error'
      error.value = '缺少有效文件或预览授权提供器'
      return
    }
    status.value = 'loading'
    controller = new AbortController()
    try {
      const result = await loadPreview(file, { signal: controller.signal })
      const blob = result instanceof Blob ? result : result?.blob
      if (!(blob instanceof Blob)) throw new Error('预览服务未返回有效文件内容')
      if (currentGeneration !== generation) return
      objectUrl.value = URL.createObjectURL(blob)
      mimeType.value = blob.type || file.mimeType || ''
      status.value = 'ready'
    } catch (e) {
      if (e?.name === 'AbortError' || currentGeneration !== generation) return
      status.value = 'error'
      error.value = e?.message || '文件暂不可预览'
    }
  }

  function retry(file) { return open(file) }

  onBeforeUnmount(() => {
    generation += 1
    release()
  })

  return { status, objectUrl, error, mimeType, activeIdentity, open, retry, release }
}
