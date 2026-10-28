import { request } from '@/services/http/client'

const ROOT = '/internship/recruitment-campaigns'
function volunteerView(row) {
  if (!row) return row
  const decision = item => item ? { ...item,
    statusLabel: ({ PENDING:'待企业处理', INTERESTED:'企业感兴趣', INTERVIEW:'邀请面试', ACCEPT_INTENT:'拟接收', REJECTED:'不合适' })[item.status] || '状态待确认',
    effectLabel: ({ ACTIVE:row.status === 'NEEDS_REVISION' ? '退回前的企业意见' : '当前有效', EXPIRED:'已过期', SUPERSEDED:'已失效', CONSUMED:'学校已确认' })[item.effectStatus] || '效力待确认'
  } : null
  return { ...row, statusLabel: ({ DRAFT:'学生草稿', SUBMITTED:'已投递', LOCKED:'企业拟接收', NEEDS_REVISION:'待学生补正', APPROVED:'岗位已确认', CLOSED:'已关闭' })[row.status] || '状态待确认',
    volunteers:(row.volunteers || []).map(item => ({ ...item, enterpriseDecision:decision(item.enterpriseDecision) })),
    decisionHistory:(row.decisionHistory || []).map(decision) }
}
export const schoolVolunteerApi = {
  context: (batchId) => request(`${ROOT}/review-context`, { params: { batchId } }),
  list: async (campaignId, params) => { const result = await request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups`, { params }); return { ...result, items:result.items?.map(volunteerView) } },
  detail: async (campaignId, groupId) => volunteerView(await request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups/${encodeURIComponent(groupId)}`)),
  confirm: async (campaignId, groupId, body) => volunteerView(await request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups/${encodeURIComponent(groupId)}/confirm`, { method: 'POST', body })),
  return: async (campaignId, groupId, body) => volunteerView(await request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups/${encodeURIComponent(groupId)}/return`, { method: 'POST', body }))
}
