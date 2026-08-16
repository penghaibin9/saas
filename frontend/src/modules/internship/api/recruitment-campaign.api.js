/**
 * 岗位实习中心 · 招聘季（招募活动）与企业参与 API（生产级：仅走真实后端，不回退 mock）。
 * 真实接口 /api/v1/internship/recruitment-campaigns/*，见后端
 * app/modules/internship/routers/internship_recruitment_campaign.py。
 *
 * 乐观锁：后端所有状态迁移与撤销均要求 expectedVersion，冲突返回 DATA_CONFLICT，
 * 调用方须把最新 version 回填后重试，不得自行猜测版本号。
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

const ROOT = '/internship/recruitment-campaigns'

export const recruitmentCampaignApi = {
  getCampaigns(params = {}) {
    return call(() =>
      request(ROOT, { params }).then((d) => ({
        list: d.items || [],
        page: d.page || 1,
        pageSize: d.pageSize || 20,
        hasMore: !!d.hasMore
      }))
    )
  },

  getCampaignDetail(id) {
    return call(() => request(`${ROOT}/${id}`))
  },

  createCampaign(body) {
    return call(() => request(ROOT, { method: 'POST', body }))
  },

  updateCampaign(id, body) {
    return call(() => request(`${ROOT}/${id}`, { method: 'PUT', body }))
  },

  /** 状态迁移：open / freeze / close / archive，均需 expectedVersion */
  transitionCampaign(id, action, expectedVersion) {
    return call(() => request(`${ROOT}/${id}/${action}`, { method: 'POST', body: { expectedVersion } }))
  },

  /** 招聘季内已邀请企业清单；status 可选 INVITED / ACCEPTED / DECLINED / REVOKED / SUSPENDED */
  getCampaignEnterprises(campaignId, params = {}) {
    return call(() =>
      request(`${ROOT}/${campaignId}/enterprises`, { params }).then((d) => ({
        list: d.items || [],
        page: d.page || 1,
        pageSize: d.pageSize || 20,
        hasMore: !!d.hasMore
      }))
    )
  },

  /**
   * 邀请企业加入招聘季。
   * 返回体含一次性 inviteToken（后端仅存哈希），须由学校侧转交企业联系人完成激活，
   * 页面只在本次响应内展示，不做任何本地持久化。
   */
  inviteEnterprise(campaignId, body) {
    return call(() => request(`${ROOT}/${campaignId}/enterprises/invite`, { method: 'POST', body }))
  },

  revokeEnterprise(campaignId, companyId, { expectedVersion, reason }) {
    return call(() =>
      request(`${ROOT}/${campaignId}/enterprises/${companyId}/revoke`, {
        method: 'POST',
        body: { expectedVersion, reason }
      })
    )
  }
}

export default recruitmentCampaignApi
