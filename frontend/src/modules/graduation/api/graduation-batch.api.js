/**
 * 毕业设计中心 · 毕设批次 API（生产级：仅走真实后端，不回退 mock）。
 * 端点 /graduation/batches/*。Excel 台账导出经 base64 返回，前端 downloadXlsxFromApi 触发下载。
 * 独立文件，与毕业设计域其它 api 隔离；不依赖实习/迎新模块。
 */
import { request } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const BASE = '/graduation/batches'

export const graduationBatchApi = {
  getBatches(params = {}) {
    return callList(BASE, params)
  },
  getBatchDetail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  createBatch(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  updateBatch(id, body) {
    return call(() => request(`${BASE}/${id}`, { method: 'PUT', body }))
  },
  setStages(id, stages) {
    return call(() => request(`${BASE}/${id}/stages`, { method: 'POST', body: { stages } }))
  },
  setRules(id, rules) {
    return call(() => request(`${BASE}/${id}/rules`, { method: 'POST', body: { rules } }))
  },
  activateBatch(id) {
    return call(() => request(`${BASE}/${id}/activate`, { method: 'POST' }))
  },
  closeBatch(id) {
    return call(() => request(`${BASE}/${id}/close`, { method: 'POST' }))
  },
  archiveBatch(id) {
    return call(() => request(`${BASE}/${id}/archive`, { method: 'POST' }))
  },
  voidBatch(id, reason) {
    return call(() => request(`${BASE}/${id}/void`, { method: 'POST', body: { reason } }))
  },
  getStats() {
    return call(() => request(`${BASE}/stats`))
  },
  exportBatches(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
  },
  async downloadBatchExport(params = {}) {
    const res = await this.exportBatches(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '毕设批次台账.xlsx')
    return res
  }
}

export default graduationBatchApi
