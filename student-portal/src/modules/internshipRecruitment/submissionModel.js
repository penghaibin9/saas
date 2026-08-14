import { buildVolunteerSubmitPayload } from './selectionContract.js'

export const VOLUNTEER_STATUS_META = Object.freeze({
  DRAFT: { label: '志愿待提交', tone: 'neutral' },
  SUBMITTED: { label: '志愿已提交', tone: 'info' },
  LOCKED: { label: '等待学校最终确认', tone: 'warning' },
  NEEDS_REVISION: { label: '可重新调整', tone: 'warning' },
  APPROVED: { label: '学校已确认', tone: 'success' },
  CONFIRMED: { label: '学校已确认', tone: 'success' }
})

export function canSubmitVolunteerGroup(group) {
  return ['DRAFT', 'NEEDS_REVISION'].includes(String(group?.status || '').toUpperCase())
}

export function canWithdrawVolunteerGroup(group) {
  return String(group?.status || '').toUpperCase() === 'SUBMITTED'
}

export function canRequestVolunteerUnlock(group) {
  return String(group?.status || '').toUpperCase() === 'LOCKED'
}

export function formatSchoolConfirmDeadline(value) {
  if (!value) return '待学校公布'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }).format(date)
}

export function buildVolunteerFinalSubmitRequest({ group, preview, contactSharingMode }) {
  return buildVolunteerSubmitPayload({
    expectedGroupVersion: Number(group?.version || 0),
    expectedProfileVersion: Number(preview?.profileVersion || 0),
    consentPolicyVersion: String(preview?.consentPolicyVersion || ''),
    contactSharingMode,
    confirmMaterialPreviewHash: String(preview?.previewHash || '')
  })
}

export function normalizeVolunteerSubmitError(error = {}) {
  const details = error?.details || {}
  const invalidItems = Array.isArray(error?.invalidItems)
    ? error.invalidItems
    : Array.isArray(details?.invalidItems)
      ? details.invalidItems
      : []
  return {
    code: String(error?.bizCode || error?.code || ''),
    message: error?.message || '整组投递失败，请检查后重试',
    invalidItems: invalidItems.map((item) => ({
      volunteerNo: Number(item.volunteerNo || 0),
      positionId: item.positionId ?? null,
      reason: String(item.reason || item.message || '岗位当前不可提交')
    }))
  }
}

export function submissionStateMessage(group = {}) {
  const status = String(group.status || 'DRAFT').toUpperCase()
  if (status === 'LOCKED') {
    return group.lockedCompanyName
      ? `${group.lockedCompanyName} 已拟接收，等待学校最终确认`
      : '企业已拟接收，等待学校最终确认'
  }
  if (status === 'NEEDS_REVISION') return '当前已恢复为可调整状态；旧拟接收处理仅保留在历史记录中。'
  if (status === 'SUBMITTED') return '志愿已整组投递，企业正在处理。尚未产生拟接收前可整组撤回修改。'
  if (['APPROVED', 'CONFIRMED'].includes(status)) return '学校已完成最终确认，正式落岗结果以实习记录为准。'
  return '确认志愿顺序、岗位申请说明和企业共享材料后，可整组投递。'
}
