/**
 * 毕业设计中心 · 问题预警 / 毕设归档 / 毕设统计 API。
 * 学校端始终携带当前批次；批量归档执行必须消费老师刚刚确认的后端签名预览令牌，禁止静默二次预览。
 */
import { request } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { withGraduationBatch as withBatch } from '@/modules/graduation/api/graduation-batch-context'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1, data = null) { return Promise.resolve({ code, data, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params: withBatch(params) })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const RISK = '/graduation/gd-risks'
const ARCHIVE = '/graduation/gd-archives'
const STATS = '/graduation/gd-stats'
const pendingArchivePreviews = new Map()

function previewKey(mode, scoped = {}) {
  return `${mode}:${String(scoped.batchId || '')}`
}

function rememberPreview(mode, scoped, data) {
  if (!data?.previewToken) return
  pendingArchivePreviews.set(previewKey(mode, scoped), {
    previewToken: data.previewToken,
    archiveBatchNo: data.archiveBatchNo || '',
  })
}

function consumePreview(mode, scoped, body = {}) {
  const key = previewKey(mode, scoped)
  const cached = pendingArchivePreviews.get(key) || {}
  pendingArchivePreviews.delete(key)
  return {
    previewToken: body.previewToken || cached.previewToken || '',
    archiveBatchNo: body.archiveBatchNo || cached.archiveBatchNo || '',
  }
}

export const graduationRiskArchiveApi = {
  scanRisks(params = {}) { return call(() => request(`${RISK}/scan`, { method: 'POST', params: withBatch(params) })) },
  getLastRiskScan(params = {}) { return call(() => request(`${RISK}/last-scan`, { params: withBatch(params) })) },
  getRiskList(params = {}) { return callList(RISK, params) },
  getArchiveByStudent(gdStudentId, params = {}) {
    return call(() => request(`${ARCHIVE}/${gdStudentId}`, { params: withBatch(params) }))
  },
  getRiskStats(params = {}) { return call(() => request(`${RISK}/stats`, { params: withBatch(params) })) },
  acceptRisk(id, assignee, params = {}) {
    return call(() => request(`${RISK}/${id}/accept`, { method: 'POST', params: withBatch(params), body: { assignee } }))
  },
  processRisk(id, note, params = {}) {
    return call(() => request(`${RISK}/${id}/process`, { method: 'POST', params: withBatch(params), body: { note } }))
  },
  closeRisk(id, reason, params = {}) {
    return call(() => request(`${RISK}/${id}/close`, { method: 'POST', params: withBatch(params), body: { reason } }))
  },

  getArchiveList(params = {}) { return callList(ARCHIVE, params) },
  getArchiveStats(params = {}) { return call(() => request(`${ARCHIVE}/stats`, { params: withBatch(params) })) },
  async previewBatchGenerate(params = {}) {
    const scoped = withBatch(params)
    try {
      const data = await request(`${ARCHIVE}/batch-generate/preview`, { method: 'POST', params: scoped })
      rememberPreview('GENERATE', scoped, data)
      return ok(data)
    } catch (e) { return toErr(e) }
  },
  async batchGenerateArchive(params = {}, body = {}) {
    const scoped = withBatch(params)
    const preview = consumePreview('GENERATE', scoped, body)
    if (!preview.previewToken) return fail('归档预览执行凭证不存在或已消费，请重新预览', 409)
    try {
      return ok(await request(`${ARCHIVE}/batch-generate`, {
        method: 'POST', params: scoped, body: { ...body, previewToken: preview.previewToken },
      }))
    } catch (e) { return toErr(e) }
  },
  async previewBatchFile(params = {}, body = {}) {
    const scoped = withBatch(params)
    try {
      const data = await request(`${ARCHIVE}/batch-file/preview`, {
        method: 'POST', params: scoped, body: { archiveBatchNo: body.archiveBatchNo || undefined },
      })
      rememberPreview('FILE', scoped, data)
      return ok(data)
    } catch (e) { return toErr(e) }
  },
  async batchFileArchive(params = {}, body = {}) {
    const scoped = withBatch(params)
    const preview = consumePreview('FILE', scoped, body)
    if (!preview.previewToken || !preview.archiveBatchNo) {
      return fail('备案预览执行凭证不存在、不完整或已消费，请重新预览', 409)
    }
    try {
      const data = await request(`${ARCHIVE}/batch-file`, {
        method: 'POST', params: scoped,
        body: { ...body, archiveBatchNo: preview.archiveBatchNo, previewToken: preview.previewToken },
      })
      const failed = Number(data?.failed || 0)
      if (failed > 0) {
        const first = data?.errors?.[0]?.message
        const message = `批量备案部分失败：成功 ${Number(data?.filed || 0)}，跳过 ${Number(data?.skipped || 0)}，失败 ${failed}${first ? `；首个失败：${first}` : ''}`
        return fail(message, 409, data)
      }
      return ok(data)
    } catch (e) { return toErr(e) }
  },
  generateArchive(gdStudentId, params = {}) {
    return call(() => request(`${ARCHIVE}/${gdStudentId}/generate`, { method: 'POST', params: withBatch(params) }))
  },
  submitArchive(gdStudentId, params = {}) {
    return call(() => request(`${ARCHIVE}/${gdStudentId}/submit`, { method: 'POST', params: withBatch(params) }))
  },
  fileArchive(gdStudentId, archiveBatchNo, params = {}) {
    return call(() => request(`${ARCHIVE}/${gdStudentId}/file`, {
      method: 'POST', params: withBatch(params), body: { archiveBatchNo },
    }))
  },
  rejectArchive(gdStudentId, reason, params = {}) {
    return call(() => request(`${ARCHIVE}/${gdStudentId}/reject`, {
      method: 'POST', params: withBatch(params), body: { reason },
    }))
  },
  exportArchives(params = {}) {
    return call(() => request(`${ARCHIVE}/export`, { method: 'POST', params: withBatch(params) }))
  },
  async downloadArchiveExport(params = {}) {
    const res = await this.exportArchives(params)
    if (res.code === 0) {
      const hint = params.filenameHint || params.exportHint
      const filename = res.data?.filename || (hint ? `${String(hint).replace(/\.xlsx$/i, '')}.xlsx` : '毕设归档台账.xlsx')
      downloadXlsxFromApi({ ...(res.data || {}), filename })
    }
    return res
  },

  getOverviewStats(params = {}) { return call(() => request(`${STATS}/overview`, { params: withBatch(params) })) },
  getCollegeComparison(params = {}) { return call(() => request(`${STATS}/college-comparison`, { params: withBatch(params) })) }
}

export default graduationRiskArchiveApi
