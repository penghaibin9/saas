import { request, requestBlob } from '@/services/http/client'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 1,
    bizCode: error?.bizCode || '',
    data: null,
    message: error?.message || '监管上报接口调用失败'
  }
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return fail(error)
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export const regulatoryReportingApi = {
  listTemplates(reportCode) {
    return call(() => request('/internship/regulatory-reporting/templates', {
      params: { reportCode }
    }))
  },

  createTemplateVersion(reportCode, body) {
    return call(() => request(
      `/internship/regulatory-reporting/templates/${encodeURIComponent(String(reportCode || ''))}/versions`,
      { method: 'POST', body: body || {} }
    ))
  },

  async downloadFieldDictionary(template) {
    try {
      const code = encodeURIComponent(String(template?.reportCode || ''))
      const blob = await requestBlob(
        `/internship/regulatory-reporting/templates/${code}/field-dictionary.xlsx`
      )
      downloadBlob(
        blob,
        `${template?.reportCode || 'regulatory'}-V${template?.versionNo || 1}-field-dictionary.xlsx`
      )
      return ok(true)
    } catch (error) {
      return fail(error)
    }
  },

  listTasks(params = {}) {
    return call(() => request('/internship/regulatory-reporting/tasks', { params }))
  },

  getTask(taskId) {
    return call(() => request(
      `/internship/regulatory-reporting/tasks/${encodeURIComponent(String(taskId || ''))}`
    ))
  },

  listTaskRows(taskId, params = {}) {
    return call(() => request(
      `/internship/regulatory-reporting/tasks/${encodeURIComponent(String(taskId || ''))}/rows`,
      { params }
    ))
  },

  createTask(reportCode, batchId) {
    return call(() => request('/internship/regulatory-reporting/tasks', {
      method: 'POST',
      body: { reportCode, batchId }
    }))
  },

  validateTask(taskId) {
    return call(() => request(`/internship/regulatory-reporting/tasks/${taskId}/validate`, {
      method: 'POST'
    }))
  },

  async downloadErrors(task) {
    try {
      const blob = await requestBlob(
        `/internship/regulatory-reporting/tasks/${task.id}/errors.xlsx`
      )
      downloadBlob(blob, `${task.taskNo || 'regulatory'}-errors.xlsx`)
      return ok(true)
    } catch (error) {
      return fail(error)
    }
  },

  async exportFormal(task) {
    try {
      const blob = await requestBlob(
        `/internship/regulatory-reporting/tasks/${task.id}/export.xlsx`,
        { method: 'POST' }
      )
      downloadBlob(blob, `${task.taskNo || 'regulatory'}.xlsx`)
      return ok(true)
    } catch (error) {
      return fail(error)
    }
  },

  markSubmitted(taskId, externalSubmissionRef) {
    return call(() => request(
      `/internship/regulatory-reporting/tasks/${taskId}/external-submission`,
      { method: 'POST', body: { externalSubmissionRef } }
    ))
  }
}

export default regulatoryReportingApi
