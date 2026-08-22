import { request, requestBlob, requestUpload } from '@/services/http/client'
import { requestMultipart } from '@/services/http/multipart'

const BASE = '/academic-affairs/file-exchange'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 1,
    data: null,
    message: error?.message || '教务数据交换服务不可用'
  }
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return fail(error)
  }
}

async function upload(path, file) {
  try {
    return ok(await requestUpload(path, file))
  } catch (error) {
    return fail(error)
  }
}

async function multipart(path, file, fields = {}) {
  try {
    return ok(await requestMultipart(path, { files: { file }, fields }))
  } catch (error) {
    return fail(error)
  }
}

export const academicFileExchangeApi = {
  downloadCourseCatalogTemplate() {
    return call(() => requestBlob(`${BASE}/course-catalog/import-template`))
  },

  uploadCourseCatalogImport(file) {
    return upload(`${BASE}/course-catalog/import-jobs`, file)
  },

  downloadProgramTemplate() {
    return call(() => requestBlob(`${BASE}/programs/import-template`))
  },

  uploadProgramDefinitionImport(file) {
    return upload(`${BASE}/programs/definition/import-jobs`, file)
  },

  uploadProgramBindingImport(file) {
    return upload(`${BASE}/programs/binding/import-jobs`, file)
  },

  uploadRosterImport(file) {
    return upload(`${BASE}/roster/import-jobs`, file)
  },

  uploadGradeImport(taskId, file) {
    return upload(`${BASE}/grade-tasks/${taskId}/import-jobs`, file)
  },

  uploadScheduleImport(batchId, file, importMode = 'ATOMIC') {
    const mode = String(importMode || 'ATOMIC').trim().toUpperCase()
    if (!['ATOMIC', 'PARTIAL'].includes(mode)) {
      return Promise.resolve({ code: 1, data: null, message: '导入策略仅支持 ATOMIC/PARTIAL' })
    }
    return multipart(`${BASE}/schedule-batches/${batchId}/import-jobs`, file, { importMode: mode })
  },

  confirmImport(jobId, expectedVersion) {
    return call(() => request(`${BASE}/imports/${jobId}/confirm`, {
      method: 'POST',
      body: { expectedVersion }
    }))
  },

  exportImportErrors(jobId) {
    return call(() => request(`${BASE}/imports/${jobId}/errors-export`, { method: 'POST' }))
  },

  createRosterExport(body) {
    return call(() => request(`${BASE}/roster/export-jobs`, { method: 'POST', body }))
  },

  listJobs(params = {}) {
    return call(() => request(`${BASE}/jobs`, { params }))
  },

  getImportJob(jobId) {
    return call(() => request(`${BASE}/imports/${jobId}`))
  },

  getExportJob(jobId) {
    return call(() => request(`${BASE}/exports/${jobId}`))
  },

  createExportDownloadTicket(jobId, expectedVersion) {
    return call(() => request(`${BASE}/exports/${jobId}/download-ticket`, {
      method: 'POST',
      body: { expectedVersion }
    }))
  },

  async downloadExport(downloadUrl) {
    try {
      return ok(await requestBlob(downloadUrl))
    } catch (error) {
      return fail(error)
    }
  },

  revokeExport(jobId, expectedVersion, reason) {
    return call(() => request(`${BASE}/exports/${jobId}/revoke`, {
      method: 'POST',
      body: { expectedVersion, reason }
    }))
  }
}

export default academicFileExchangeApi
