/**
 * 岗位实习中心 · 归档中心 API（生产级：仅走真实后端，不回退 mock）。
 */
import { request } from '@/services/http/client'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (e) {
    return toErr(e)
  }
}

async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) {
    return toErr(e)
  }
}

const B = '/internship/archive'

export const archiveApi = {
  getByStudent(params = {}) {
    return callList(B, params)
  },

  getDetail(id) {
    return call(() => request(`${B}/${id}`))
  },

  byBatch(params = {}) {
    return call(() => request(`${B}/by-batch`, { params }))
  },

  byEnterprise(params = {}) {
    return call(() => request(`${B}/by-enterprise`, { params }))
  },

  archive(id, { force, expectedVersion, version, recordVersion } = {}) {
    return call(() => request(`${B}/${id}/archive`, {
      method: 'POST',
      body: {
        force: !!force,
        expectedVersion: expectedVersion ?? version ?? recordVersion
      }
    }))
  },

  revoke(id, { reason, expectedVersion, version }) {
    return call(() => request(`${B}/${id}/revoke`, {
      method: 'POST', body: { reason, expectedVersion: expectedVersion ?? version }
    }))
  },

  exportArchives(params = {}) {
    return call(() => request(`${B}/export`, { method: 'POST', params }))
  },

  buildPackage(id) {
    return call(() => request(`${B}/${id}/package`, { method: 'POST' }))
  }
}
