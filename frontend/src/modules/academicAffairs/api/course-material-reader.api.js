import { request } from '@/services/http/client'
import fileSdk from '@/services/file/fileSdk'

const enc = encodeURIComponent

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

function normalizeMaterial(item = {}) {
  const allowedActions = Array.isArray(item.allowedActions) ? item.allowedActions : []
  return {
    ...item,
    fileId: String(item.fileId || ''),
    materialId: String(item.materialId || item.id || ''),
    fileName: item.fileName || item.title || '课程材料',
    canPreview: allowedActions.includes('preview'),
    canDownload: allowedActions.includes('download')
  }
}

/**
 * 教务课程材料 Reader adapter。
 * 业务关系由 courseId + materialId 锁定；预览/下载只消费后端签发的课程材料短时票据，
 * 不把课程附件降级成 generic File Center URL。
 */
export const courseMaterialReaderApi = {
  async list(courseId) {
    const data = await request(`/academic-affairs/courses/${enc(courseId)}/materials/reader`)
    return (data?.items || []).map(normalizeMaterial)
  },

  issueTicket(courseId, materialId, action = 'preview') {
    return request(`/academic-affairs/courses/${enc(courseId)}/materials/${enc(materialId)}/ticket`, {
      method: 'POST',
      body: { action }
    })
  },

  createPreviewProvider(courseId) {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        if (!descriptor?.materialId) throw new Error('课程材料缺少 materialId，拒绝越过业务关系预览')
        const ticket = await raceAbort(
          courseMaterialReaderApi.issueTicket(courseId, descriptor.materialId, 'preview'),
          signal
        )
        return raceAbort(fileSdk.blobFrom(ticketPath(ticket)), signal)
      },
      dispose() {}
    }
  },

  async download(courseId, material = {}) {
    if (!material?.materialId) throw new Error('课程材料缺少 materialId，拒绝越过业务关系下载')
    const ticket = await this.issueTicket(courseId, material.materialId, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), material.fileName || '课程材料')
  }
}

export default courseMaterialReaderApi
