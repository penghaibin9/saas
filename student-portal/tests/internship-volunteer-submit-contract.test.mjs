import test from 'node:test'
import assert from 'node:assert/strict'

import {
  VOLUNTEER_STATUS_META,
  buildVolunteerFinalSubmitRequest,
  canRequestVolunteerUnlock,
  canSubmitVolunteerGroup,
  canWithdrawVolunteerGroup,
  normalizeVolunteerSubmitError,
  submissionStateMessage
} from '../src/modules/internshipRecruitment/submissionModel.js'

test('A03-8 submits one group using server preview/version evidence', () => {
  const payload = buildVolunteerFinalSubmitRequest({
    group: { version: 12 },
    preview: {
      profileVersion: 8,
      consentPolicyVersion: 'INTERN_APPLICATION_PRIVACY_2026_08',
      previewHash: 'sha256:abc'
    },
    contactSharingMode: 'AFTER_INTERVIEW'
  })
  assert.deepEqual(payload, {
    expectedGroupVersion: 12,
    expectedProfileVersion: 8,
    consentPolicyVersion: 'INTERN_APPLICATION_PRIVACY_2026_08',
    contactSharingMode: 'AFTER_INTERVIEW',
    confirmMaterialPreviewHash: 'sha256:abc'
  })
})

test('A03-8 action boundaries follow DRAFT/SUBMITTED/LOCKED/NEEDS_REVISION', () => {
  assert.equal(canSubmitVolunteerGroup({ status: 'DRAFT' }), true)
  assert.equal(canSubmitVolunteerGroup({ status: 'NEEDS_REVISION' }), true)
  assert.equal(canSubmitVolunteerGroup({ status: 'SUBMITTED' }), false)
  assert.equal(canWithdrawVolunteerGroup({ status: 'SUBMITTED' }), true)
  assert.equal(canWithdrawVolunteerGroup({ status: 'LOCKED' }), false)
  assert.equal(canRequestVolunteerUnlock({ status: 'LOCKED' }), true)
  assert.equal(canRequestVolunteerUnlock({ status: 'DRAFT' }), false)
})

test('A03-8 LOCKED and NEEDS_REVISION explain why editing changed', () => {
  assert.match(submissionStateMessage({ status: 'LOCKED', lockedCompanyName: '中联重科' }), /中联重科 已拟接收/)
  assert.match(submissionStateMessage({ status: 'NEEDS_REVISION' }), /旧拟接收处理仅保留在历史记录/)
})

test('A03-11 canonical APPROVED is a final school-confirmed state', () => {
  assert.equal(VOLUNTEER_STATUS_META.APPROVED.label, '学校已确认')
  assert.equal(VOLUNTEER_STATUS_META.CONFIRMED.label, '学校已确认')
  assert.equal(canSubmitVolunteerGroup({ status: 'APPROVED' }), false)
  assert.equal(canWithdrawVolunteerGroup({ status: 'APPROVED' }), false)
  assert.equal(canRequestVolunteerUnlock({ status: 'APPROVED' }), false)
  assert.match(submissionStateMessage({ status: 'APPROVED' }), /学校已完成最终确认/)
})

test('A03-11 unavailable authority state exposes no write action', () => {
  assert.equal(VOLUNTEER_STATUS_META.UNAVAILABLE.label, '志愿暂不可用')
  assert.equal(canSubmitVolunteerGroup({ status: 'UNAVAILABLE' }), false)
  assert.equal(canWithdrawVolunteerGroup({ status: 'UNAVAILABLE' }), false)
  assert.equal(canRequestVolunteerUnlock({ status: 'UNAVAILABLE' }), false)
  assert.match(submissionStateMessage({ status: 'UNAVAILABLE' }), /不会用本地数据替代学校记录/)
})

test('A03-8 invalid job response remains whole-group failure and exposes every item', () => {
  const result = normalizeVolunteerSubmitError({
    bizCode: 'VOLUNTEER_POSITION_INVALID',
    message: '部分岗位已失效',
    details: {
      invalidItems: [
        { volunteerNo: 2, positionId: 203, reason: '岗位已下架' },
        { volunteerNo: 3, positionId: 218, reason: '岗位名额已满' }
      ]
    }
  })
  assert.equal(result.code, 'VOLUNTEER_POSITION_INVALID')
  assert.equal(result.invalidItems.length, 2)
  assert.deepEqual(result.invalidItems.map((item) => item.volunteerNo), [2, 3])
  assert.equal(result.invalidItems[0].reason, '岗位已下架')
})
