/**
 * 毕业设计中心 · 问题预警 / 毕设归档 / 毕设统计 API。
 * 学校端始终携带当前批次；批量归档执行必须绑定后端签名预览令牌。
 */
import { request } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
function withBatch(params = {}) {
  const store = useGraduationBatchStore()
  const batchId = params.batchId || store.selectedBatchId
  if (!batchId) throw new Error('请先选择毕业设计批次')
  return { ...params, batchId: String(batchId) }
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
  previewBatchGenerate(params = {}) {
    return call(() => request(`${ARCHIVE}/batch-generate/preview`, { method: 'POST', params: withBatch(params) }))
  },
  async batchGenerateArchive(params = {}, body = {}) {
    const scoped = withBatch(params)
    try {
      let previewToken = body.previewToken
      if (!previewToken) {
        const preview = await request(`${ARCHIVE}/batch-generate/preview`, { method: 'POST', params: scoped })
        previewToken = preview.previewToken
      }
      if (!previewToken) return fail('归档预览未生成执行凭证，请重新预览', 409)
      return ok(await request(`${ARCHIVE}/batch-generate`, {
        method: 'POST', params: scoped, body: { ...body, previewToken },
      }))
    } catch (e) { return toErr(e) }
  },
  previewBatchFile(params = {}, body = {}) {
    return call(() => request(`${ARCHIVE}/batch-file/preview`, {
      method: 'POST', params: withBatch(params), body: { archiveBatchNo: body.archiveBatchNo || undefined },
    }))
  },
  async batchFileArchive(params = {}, body = {}) {
    const scoped = withBatch(params)
    try {
      let previewToken = body.previewToken
      let archiveBatchNo = body.archiveBatchNo
      if (!previewToken) {
        const preview = await request(`${ARCHIVE}/batch-file/preview`, {
          method: 'POST', params: scoped, body: { archiveBatchNo: archiveBatchNo || undefined },
        })
        previewToken = preview.previewToken
        archiveBatchNo = preview.archiveBatchNo
      }
      if (!previewToken || !archiveBatchNo) return fail('备案预览未生成完整执行凭证，请重新预览', 409)
      return ok(await request(`${ARCHIVE}/batch-file`, {
        method: 'POST', params: scoped, body: { ...body, archiveBatchNo, previewToken },
      }))
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
