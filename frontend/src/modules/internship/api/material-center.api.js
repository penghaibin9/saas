import { request } from '@/services/http/client'
import fileSdk from '@/services/file/fileSdk'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'

const BASE = '/internship/material-center'

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

export const internshipMaterialCenterApi = {
  list(params = {}) { return request(BASE, { params }) },
  detail(internshipId) { return request(`${BASE}/${encodeURIComponent(internshipId)}`) },
  sync(internshipId) {
    return request(`${BASE}/${encodeURIComponent(internshipId)}/sync`, { method: 'POST' })
  },
  manifest(internshipId) { return request(`${BASE}/${encodeURIComponent(internshipId)}/manifest`) },
  issueMaterialTicket(fileId, action = 'preview') {
    return request(`${BASE}/files/${encodeURIComponent(fileId)}/ticket`, {
      method: 'POST', body: { action }
    })
  },
  previewDescriptor(item = {}) {
    return buildPreviewDescriptorFromFile({
      ...item,
      fileVersionId: item.fileVersionId ?? item.versionId ?? null,
      sourceSha256: item.sourceSha256 || item.sha256 || '',
      materialName: item.categoryLabel || item.title || item.fileName,
      allowedActions: ['preview', ...(item.canDownload ? ['download'] : [])]
    })
  },
  createPreviewProvider() {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        const ticket = await raceAbort(
          internshipMaterialCenterApi.issueMaterialTicket(descriptor.fileId, 'preview'), signal
        )
        return raceAbort(fileSdk.blobFrom(ticketPath(ticket)), signal)
      },
      dispose() {}
    }
  },
  async downloadMaterial(item = {}) {
    const ticket = await this.issueMaterialTicket(item.fileId, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), item.fileName || '实习材料')
  }
}

export default internshipMaterialCenterApi
