import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import { getToken, request } from '@/services/http/client'
import fileSdk, { normalizeFile } from '@/services/file/fileSdk'
import { buildPreviewDescriptorFromFile, previewSourceByteLimit } from '@/components/file/viewer/viewer-contract'

const PREVIEW_FETCH_TIMEOUT_MS = 15000

function ticketPath(ticket = {}) {
  const value = String(ticket.url || ticket.downloadUrl || '')
  if (!value.startsWith('/api/v1/')) return value
  return value.slice('/api/v1'.length)
}

function abortError() {
  const error = new Error('预览已切换')
  error.name = 'AbortError'
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

function previewError(code, message, extra = {}) {
  return Object.assign(new Error(message), {
    code,
    bizCode: extra.bizCode,
    details: extra.details,
    retryable: extra.retryable ?? false
  })
}

function createPreviewFetchScope(externalSignal) {
  const controller = new AbortController()
  let timedOut = false
  const onAbort = () => controller.abort()
  if (externalSignal?.aborted) controller.abort()
  else externalSignal?.addEventListener('abort', onAbort, { once: true })
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, PREVIEW_FETCH_TIMEOUT_MS)
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    externalAborted: () => Boolean(externalSignal?.aborted),
    cleanup() {
      clearTimeout(timer)
      externalSignal?.removeEventListener('abort', onAbort)
    }
  }
}

async function readBoundedPreviewBlob(response, descriptor, signal) {
  const limit = previewSourceByteLimit(descriptor)
  const declared = Number(response.headers.get('content-length') || 0)
  if (limit && declared > limit) {
    try { await response.body?.cancel() } catch { /* best effort */ }
    throw previewError('PREVIEW_TOO_LARGE', '文件超过站内阅读大小上限，请下载原文查看')
  }
  if (!response.body?.getReader || !limit) return response.blob()
  const reader = response.body.getReader()
  const chunks = []
  let total = 0
  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel('preview aborted').catch(() => {})
        throw abortError()
      }
      const { done, value } = await reader.read()
      if (done) break
      if (!value?.byteLength) continue
      total += value.byteLength
      if (total > limit) {
        await reader.cancel('preview byte budget exceeded').catch(() => {})
        throw previewError('PREVIEW_TOO_LARGE', '文件超过站内阅读大小上限，请下载原文查看')
      }
      chunks.push(value)
    }
  } catch (error) {
    if (signal?.aborted || error?.name === 'AbortError') throw abortError()
    throw error
  } finally {
    try { reader.releaseLock() } catch { /* stream already closed */ }
  }
  return new Blob(chunks, { type: response.headers.get('content-type') || 'application/octet-stream' })
}

async function fetchPreviewBlob(path, descriptor, signal, retried = false) {
  if (!path || typeof path !== 'string' || !path.startsWith('/')) {
    throw previewError('INVALID_AUTHORIZED_FILE_PATH', '服务端未返回有效文件授权路径')
  }
  if (signal?.aborted) throw abortError()
  const fetchScope = createPreviewFetchScope(signal)
  const token = getToken()
  try {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      method: 'GET',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
      signal: fetchScope.signal
    })
    if (response.status === 401 && !retried) {
      try { await response.body?.cancel() } catch { /* best effort */ }
      await raceAbort(request('/auth/me'), fetchScope.signal)
      return fetchPreviewBlob(path, descriptor, signal, true)
    }
    if (!response.ok) {
      const payload = await response.clone().json().catch(() => null)
      throw previewError(payload?.code || response.status, payload?.message || `预览读取失败（HTTP ${response.status}）`, {
        bizCode: payload?.bizCode,
        details: payload?.details
      })
    }
    return await readBoundedPreviewBlob(response, descriptor, fetchScope.signal)
  } catch (error) {
    if (signal?.aborted || fetchScope.externalAborted()) throw abortError()
    if (fetchScope.timedOut()) {
      throw previewError('PREVIEW_FETCH_TIMEOUT', '预览读取超时，请重试', { retryable: true })
    }
    if (error?.name === 'AbortError') {
      throw previewError('PREVIEW_FETCH_INTERRUPTED', '预览读取被浏览器中断，请重试', { retryable: true })
    }
    throw error
  } finally {
    fetchScope.cleanup()
  }
}

export const graduationMaterialCenterApi = {
  listRules(batchId) {
    return request('/graduation/material-center/rules', { params: batchId ? { batchId } : {} })
  },
  createRule(payload) {
    return request('/graduation/material-center/rules', { method: 'POST', data: payload })
  },
  ruleImpact(ruleId) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/impact`)
  },
  activateRule(ruleId, { confirmCatalogRepair = false, expectedVersion } = {}) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/activate`, {
      method: 'POST', data: { confirmCatalogRepair, expectedVersion }
    })
  },
  overview(params = {}) { return request('/graduation/material-center/overview', { params }) },
  files(params = {}) { return request('/graduation/material-center/files', { params }) },
  students(params = {}) { return request('/graduation/material-center/students', { params }) },
  summary(params = {}) { return request('/graduation/material-center/summary', { params }) },
  backfill({ pageSize = 200, cursorModel = 'PROPOSAL', cursorId = 0, dryRun = false } = {}) {
    return request('/graduation/material-center/backfill', { method: 'POST', data: { pageSize, cursorModel, cursorId, dryRun } })
  },
  studentLibrary(gdStudentId, includeHistory = true) {
    return request(`/graduation/material-center/students/${encodeURIComponent(gdStudentId)}/library`, { params: { includeHistory } })
  },
  submitMaterial(materialCode, { fileId, expectedVersion } = {}) {
    return request(`/graduation/material-center/materials/${encodeURIComponent(materialCode)}/submit`, { method: 'POST', data: { fileId, expectedVersion } })
  },
  reviewMaterial(materialId, { fileVersionId, expectedVersion, action, comment } = {}) {
    return request(`/graduation/material-center/materials/${encodeURIComponent(materialId)}/review`, { method: 'POST', data: { fileVersionId, expectedVersion, action, comment } })
  },
  proposalVersions(proposalId) { return request(`/graduation/material-center/proposals/${encodeURIComponent(proposalId)}/versions`) },
  finalVersions(finalId) { return request(`/graduation/material-center/finals/${encodeURIComponent(finalId)}/versions`) },
  manifest(gdStudentId) { return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/manifest`) },
  freezeManifest(gdStudentId, archiveBatchNo) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/manifest`, { method: 'POST', data: { archiveBatchNo } })
  },
  revokeManifest(gdStudentId, reason) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/revoke`, { method: 'POST', data: { reason } })
  },
  buildStudentPackage(gdStudentId) { return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/package`, { method: 'POST' }) },
  buildBatchPackage(batchId) { return request(`/graduation/material-center/batches/${encodeURIComponent(batchId)}/package`, { method: 'POST' }) },
  createExport(payload) { return request('/graduation/material-center/exports', { method: 'POST', data: payload }) },
  exportJob(jobId) { return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}`) },
  retryExport(jobId) { return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/retry`, { method: 'POST' }) },
  exportTicket(jobId, expectedVersion) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/ticket`, { method: 'POST', data: { expectedVersion } })
  },
  revokeExport(jobId, expectedVersion, reason) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/revoke`, { method: 'POST', data: { expectedVersion, reason } })
  },
  templateCatalog(batchId) { return request('/graduation/material-center/templates', { params: batchId ? { batchId } : {} }) },
  publishTemplateAsset(templateId, fileId, payload = {}) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/asset`, { method: 'POST', data: { ...payload, fileId } })
  },
  setTemplateStatus(policyId, enabled, expectedVersion) {
    return request(`/graduation/material-center/templates/policies/${encodeURIComponent(policyId)}/status`, { method: 'POST', data: { enabled, expectedVersion } })
  },
  templateVersions(templateId) { return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/versions`) },
  normalizeVersions(items = []) {
    return items.map((item) => normalizeFile({ ...item, statusText: item.readyForBusiness ? '安全可用' : (item.scanStatus || item.status || '暂不可使用') }))
  },
  issueMaterialTicket(fileId, action = 'preview') {
    return request(`/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`, { method: 'POST', body: { action } })
  },
  previewDescriptor(item = {}) {
    return buildPreviewDescriptorFromFile({
      ...item,
      fileVersionId: item.fileVersionId ?? item.versionId ?? null,
      sourceSha256: item.sourceSha256 || item.sha256 || '',
      allowedActions: ['preview', ...(item.canDownload ? ['download'] : [])]
    })
  },
  createPreviewProvider() {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        const ticket = await raceAbort(graduationMaterialCenterApi.issueMaterialTicket(descriptor.fileId, 'preview'), signal)
        return fetchPreviewBlob(ticketPath(ticket), descriptor, signal)
      },
      dispose() {}
    }
  },
  async previewMaterial(item) {
    const ticket = await this.issueMaterialTicket(item.fileId, 'preview')
    return fileSdk.previewFrom(ticketPath(ticket))
  },
  async downloadMaterial(item) {
    const ticket = await this.issueMaterialTicket(item.fileId, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), item.fileName)
  },
  async downloadExport(job) {
    const ticket = await this.exportTicket(job.id, job.version)
    return fileSdk.downloadFrom(ticketPath(ticket), job?.result?.zipFileName || '毕业设计归档包.zip')
  },
  async downloadPackage(fileId, fileName) {
    const ticket = await request(`/graduation/material-center/packages/${encodeURIComponent(fileId)}/ticket`, { method: 'POST' })
    return fileSdk.downloadFrom(ticketPath(ticket), fileName)
  }
}

export default graduationMaterialCenterApi
