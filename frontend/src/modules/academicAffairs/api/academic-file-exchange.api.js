import { request, requestBlob, requestUpload } from '@/services/http/client'

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

export const academicFileExchangeApi = {
  uploadRosterImport(file) {
    return upload(`${BASE}/roster/import-jobs`, file)
  },

  uploadGradeImport(taskId, file) {
    return upload(`${BASE}/grade-tasks/${taskId}/import-jobs`, file)
  },

  uploadScheduleImport(batchId, file) {
    return upload(`${BASE}/schedule-batches/${batchId}/import-jobs`, file)
  },

  confirmImport(jobId, expectedVersion) {
    return call(() => request(`${BASE}/imports/${jobId}/confirm`, {
      method: 'POST',
      body: { expectedVersion }
    }))
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
