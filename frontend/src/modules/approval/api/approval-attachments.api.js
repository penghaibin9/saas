import { request } from '@/services/http/client'
import fileSdk from '@/services/file/fileSdk'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'

function ticketPath(ticket = {}) {
  const value = String(ticket.url || ticket.downloadUrl || '')
  if (!value.startsWith('/api/v1/')) return value
  return value.slice('/api/v1'.length)
}

function abortError() {
  const error = new DOMException('预览已切换', 'AbortError')
  error.code = 'PREVIEW_ABORTED'
  return error
}

function raceAbort(promise, signal) {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(abortError())
  return new Promise((resolve, reject) => {
    const onAbort = () => reject(abortError())
    signal.addEventListener('abort', onAbort, { once: true })
    Promise.resolve(promise).then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

export const approvalAttachmentsApi = {
  async list(taskId) {
    const data = await request(`/approvals/tasks/${encodeURIComponent(taskId)}/attachments`)
    return Array.isArray(data?.items) ? data.items : []
  },

  issueTicket(taskId, fileId, action = 'preview') {
    return request(`/approvals/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(fileId)}/ticket`, {
      method: 'POST',
      body: { action }
    })
  },

  previewDescriptor(file = {}) {
    return buildPreviewDescriptorFromFile(file)
  },

  createPreviewProvider(taskId) {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        const ticket = await raceAbort(
          approvalAttachmentsApi.issueTicket(taskId, descriptor.fileId, 'preview'),
          signal
        )
        return raceAbort(fileSdk.blobFrom(ticketPath(ticket)), signal)
      },
      dispose() {}
    }
  },

  async download(taskId, file = {}) {
    const ticket = await this.issueTicket(taskId, file.fileId, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), file.fileName || '审批附件')
  }
}

export default approvalAttachmentsApi
