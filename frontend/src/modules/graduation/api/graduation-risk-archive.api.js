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

// batch-file 在同一请求内为每位学生生成系统快照并逐份备案。签名预览令牌有效期为 10 分钟，
// 因此给正式写请求 8 分钟上限，而不是原来的 15 秒硬中断；若连接仍中断，禁止自动重放写请求，
// 改为读取归档台账按 archiveBatchNo 对账，避免“前端报失败、后端其实已部分/全部成功”的未知状态。
const BATCH_FILE_TIMEOUT_MS = 8 * 60 * 1000
const BATCH_FILE_RECONCILE_ATTEMPTS = 5
const BATCH_FILE_RECONCILE_DELAY_MS = 2000

function previewKey(mode, scoped = {}) {
  return `${mode}:${String(scoped.batchId || '')}`
}

function rememberPreview(mode, scoped, data) {
  if (!data?.previewToken) return
  pendingArchivePreviews.set(previewKey(mode, scoped), {
    previewToken: data.previewToken,
    archiveBatchNo: data.archiveBatchNo || '',
    candidateCount: Number(data.candidateCount || 0),
    executableCount: Number(data.executableCount || 0),
  })
}

function consumePreview(mode, scoped, body = {}) {
  const key = previewKey(mode, scoped)
  const cached = pendingArchivePreviews.get(key) || {}
  pendingArchivePreviews.delete(key)
  return {
    previewToken: body.previewToken || cached.previewToken || '',
    archiveBatchNo: body.archiveBatchNo || cached.archiveBatchNo || '',
    candidateCount: Number(cached.candidateCount || 0),
    executableCount: Number(cached.executableCount || 0),
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function isUncertainBatchWrite(error) {
  return error?.bizCode === 'REQUEST_TIMEOUT' || Number(error?.code) === 503002
}

async function readFiledCount(scoped, archiveBatchNo) {
  const ids = new Set()
  let page = 1
  let total = 0
  do {
    const data = await request(ARCHIVE, {
      params: { ...scoped, status: 'FILED', page, pageSize: 200 },
      forceProbe: true,
      timeoutMs: 10000,
    })
    const rows = data?.items || []
    for (const row of rows) {
      if (String(row?.archiveBatchNo || '') === String(archiveBatchNo || '')) {
        ids.add(String(row?.gdStudentId || row?.id || ''))
      }
    }
    total = Number(data?.total || 0)
    page += 1
  } while ((page - 1) * 200 < total)
  return ids.size
}

async function reconcileBatchFile(scoped, archiveBatchNo, candidateCount, executableCount) {
  const expected = Math.max(0, Number(executableCount || 0))
  let filed = 0
  let lastError = null
  for (let attempt = 0; attempt < BATCH_FILE_RECONCILE_ATTEMPTS; attempt += 1) {
    try {
      filed = await readFiledCount(scoped, archiveBatchNo)
      lastError = null
      if (filed >= expected) break
    } catch (error) {
      lastError = error
    }
    if (attempt < BATCH_FILE_RECONCILE_ATTEMPTS - 1) {
      await sleep(BATCH_FILE_RECONCILE_DELAY_MS)
    }
  }
  return {
    reconciled: true,
    complete: !lastError && filed >= expected,
    filed,
    skipped: Math.max(0, Number(candidateCount || 0) - expected),
    failed: 0,
    expectedExecutableCount: expected,
    archiveBatchNo,
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
    const { previewToken, archiveBatchNo, candidateCount, executableCount } = preview
    if (!previewToken || !archiveBatchNo) {
      return fail('备案预览执行凭证不存在、不完整或已消费，请重新预览', 409)
    }
    try {
      const data = await request(`${ARCHIVE}/batch-file`, {
        method: 'POST', params: scoped, timeoutMs: BATCH_FILE_TIMEOUT_MS,
        body: { ...body, archiveBatchNo, previewToken },
      })
      const failed = Number(data?.failed || 0)
      if (failed > 0) {
        const first = data?.errors?.[0]?.message
        const message = `批量备案部分失败：成功 ${Number(data?.filed || 0)}，跳过 ${Number(data?.skipped || 0)}，失败 ${failed}${first ? `；首个失败：${first}` : ''}`
        return fail(message, 409, data)
      }
      return ok(data)
    } catch (e) {
      if (!isUncertainBatchWrite(e)) return toErr(e)
      const reconciled = await reconcileBatchFile(
        scoped, archiveBatchNo, candidateCount, executableCount
      )
      if (reconciled.complete) return ok(reconciled)
      return fail(
        `批量备案连接中断，已自动核对 ${reconciled.filed}/${reconciled.expectedExecutableCount} 份；当前结果尚未完全确认。请刷新归档台账并重新预览，勿直接重复提交。`,
        503002,
        reconciled,
      )
    }
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