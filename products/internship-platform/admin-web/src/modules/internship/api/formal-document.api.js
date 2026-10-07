import { request, requestBlob } from '@/services/http/client'

function ok(data) { return { code: 0, data, message: 'ok' } }
function fail(error) {
  return {
    code: error?.code || 1,
    bizCode: error?.bizCode || '',
    data: null,
    message: error?.message || '正式文书接口调用失败'
  }
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return fail(error) }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export const formalDocumentApi = {
  readiness(internshipId) {
    return call(() => request(
      `/internship/formal-documents/by-internship/${encodeURIComponent(String(internshipId || ''))}/readiness`
    ))
  },
  list(internshipId) {
    return call(() => request(
      `/internship/formal-documents/by-internship/${encodeURIComponent(String(internshipId || ''))}`
    ))
  },
  generate(internshipId, documentType) {
    return call(() => request('/internship/formal-documents/generate', {
      method: 'POST',
      body: { internshipId: String(internshipId || ''), documentType }
    }))
  },
  async download(document) {
    try {
      const blob = await requestBlob(
        `/internship/formal-documents/${encodeURIComponent(String(document?.id || ''))}/download`
      )
      const filename = `${document?.documentTypeLabel || '岗位实习正式文书'}_V${document?.documentVersion || 1}.pdf`
      downloadBlob(blob, filename)
      return ok(true)
    } catch (error) {
      return fail(error)
    }
  }
}

export default formalDocumentApi
