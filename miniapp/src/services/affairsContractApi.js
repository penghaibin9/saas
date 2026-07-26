import { realRequest } from '@/services/request'

/**
 * 学工四端专用契约。
 * 所有状态变更必须显式携带页面当前 version；禁止服务层替调用方查询最新版本。
 */
export const affairsContractApi = {
  getStudentCandidates: (purpose = 'TALK') =>
    realRequest(`/mobile/teacher/affairs/student-candidates?purpose=${encodeURIComponent(purpose)}`),

  // 学生请假
  getReturnedLeave: (leaveId) => realRequest(`/mobile/affairs/leave/${leaveId}/editable`),
  updateReturnedLeave: (leaveId, data) => realRequest(`/mobile/affairs/leave/${leaveId}/returned`, {
    method: 'PUT', data
  }),
  resubmitLeave: (leaveId, version) => realRequest(`/mobile/affairs/leave/${leaveId}/resubmit`, {
    method: 'POST', data: { version }
  }),
  cancelLeave: (leaveId, proofNote, version) => realRequest(`/mobile/affairs/leave/${leaveId}/cancel`, {
    method: 'POST', data: { proofNote: proofNote || '', version }
  }),
  extendLeave: (leaveId, newEndTime, reason, version) => realRequest(`/mobile/affairs/leave/${leaveId}/extension`, {
    method: 'POST', data: { newEndTime, reason, version }
  }),

  // 学生宿舍与活动
  getDormTransferOptions: () => realRequest('/mobile/affairs/dorm/transfer-options'),
  getDormTransferRooms: (buildingId) => realRequest(`/mobile/affairs/dorm/transfer-buildings/${buildingId}/rooms`),
  getDormTransferBeds: (roomId) => realRequest(`/mobile/affairs/dorm/transfer-rooms/${roomId}/beds`),
  submitDormTransfer: (toBedId, reason) => realRequest('/mobile/affairs/dorm/transfers', {
    method: 'POST', data: { toBedId, reason }
  }),
  getMyDormTransfers: () => realRequest('/mobile/affairs/dorm/transfers/my'),
  secureActivityCheckin: (activityId, token) => realRequest(`/mobile/affairs/activities/${activityId}/secure-checkin`, {
    method: 'POST', data: { token }
  }),
  getSecondClassReport: () => realRequest('/mobile/affairs/second-class/report'),

  // 教师请假
  approveLeave: (leaveId, comment, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/approve`, {
    method: 'POST', data: { comment: comment || '', version }
  }),
  rejectLeave: (leaveId, reason, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/reject`, {
    method: 'POST', data: { reason, version }
  }),
  returnLeave: (leaveId, reason, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/return`, {
    method: 'POST', data: { reason, version }
  }),
  confirmCancelLeave: (leaveId, action, data, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/cancel-confirm`, {
    method: 'POST', data: { action, ...(data || {}), version }
  }),
  proxyCancelLeave: (leaveId, actualReturnAt, note, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/proxy-cancel`, {
    method: 'POST', data: { actualReturnAt, note: note || '', version }
  }),
  reviewLeaveExtension: (leaveId, action, reason, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/extension-approve`, {
    method: 'POST', data: { action, reason: reason || '', version }
  }),
  handleLeaveOverdue: (leaveId, handleType, note, version) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/overdue-handle`, {
    method: 'POST', data: { handleType, note, version }
  }),

  // 教师通用学工审批
  reviewAid: (applyId, action, reason, level, version) => realRequest(`/mobile/teacher/affairs/aid/${applyId}/review`, {
    method: 'POST', data: { action, reason: reason || '', level: level || undefined, version }
  }),
  reviewFunding: (applicationId, action, reason, version) => realRequest(`/mobile/teacher/affairs/funding/${applicationId}/review`, {
    method: 'POST', data: { action, reason: reason || '', version }
  }),
  reviewDiscipline: (caseId, action, reason, version) => realRequest(`/mobile/teacher/affairs/discipline/${caseId}/review`, {
    method: 'POST', data: { action, reason: reason || '', version }
  }),
  processRisk: (riskId, content, version) => realRequest(`/mobile/teacher/affairs/risk/${riskId}/process`, {
    method: 'POST', data: { content, version }
  }),
  closeRisk: (riskId, conclusion, version) => realRequest(`/mobile/teacher/affairs/risk/${riskId}/close`, {
    method: 'POST', data: { conclusion, version }
  }),

  // 教师宿舍、谈话、心理、活动签到
  reviewDormTransfer: (transferId, action, reason, version) => realRequest(`/mobile/teacher/affairs/dorm/transfers/${transferId}/review`, {
    method: 'POST', data: { action, reason: reason || '', version }
  }),
  handleDormException: (exceptionId, note, version) => realRequest(`/mobile/teacher/affairs/dorm/exceptions/${exceptionId}/handle`, {
    method: 'POST', data: { note, version }
  }),
  recordTalk: (talkId, data, version) => realRequest(`/mobile/teacher/talk/${talkId}/record`, {
    method: 'POST', data: { ...(data || {}), version }
  }),
  followTalk: (talkId, action, content, version) => realRequest(`/mobile/teacher/talk/${talkId}/follow-up`, {
    method: 'POST', data: { action, content: content || '', version }
  }),
  followMental: (referralId, content, version) => realRequest(`/mobile/teacher/mental/${referralId}/follow`, {
    method: 'POST', data: { content, version }
  }),
  escalateMental: (referralId, content, version) => realRequest(`/mobile/teacher/mental/${referralId}/escalate`, {
    method: 'POST', data: { content: content || '', version }
  }),
  closeMental: (referralId, conclusion, version) => realRequest(`/mobile/teacher/mental/${referralId}/close`, {
    method: 'POST', data: { conclusion, version }
  }),
  getOngoingActivities: () => realRequest('/mobile/teacher/affairs/activities/ongoing'),
  getActivityCheckinToken: (activityId) => realRequest(`/mobile/teacher/affairs/activities/${activityId}/checkin-token`)
}

export default affairsContractApi
