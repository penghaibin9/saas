import test from 'node:test'
import assert from 'node:assert/strict'

import {
  CONTACT_SHARING_OPTIONS,
  buildPdfPreviewRequest,
  normalizeContactSharingMode,
  normalizeMaterialPreview
} from '../src/modules/internshipRecruitment/materialPreviewModel.js'

test('A03-6 contact sharing defaults to safe AFTER_INTERVIEW policy', () => {
  assert.equal(normalizeContactSharingMode(), 'AFTER_INTERVIEW')
  assert.equal(normalizeContactSharingMode('UNKNOWN_POLICY'), 'AFTER_INTERVIEW')
  assert.equal(CONTACT_SHARING_OPTIONS.find((item) => item.value === 'AFTER_INTERVIEW')?.label, '面试后可查看')
})

test('A03-6 enterprise material preview only keeps server shared fields and policy evidence', () => {
  const preview = normalizeMaterialPreview({
    previewHash: 'sha256:abc',
    consentPolicyVersion: 'INTERN_APPLICATION_PRIVACY_2026_08',
    profileVersion: 8,
    groupVersion: 12,
    schoolFields: [{ key: 'major', label: '专业', value: '数控技术' }],
    studentFields: [{ key: 'intro', label: '自我介绍', value: '认真负责' }],
    maskedContact: '138****0000',
    volunteers: [{ companyName: '企业B' }]
  })
  assert.equal(preview.previewHash, 'sha256:abc')
  assert.equal(preview.profileVersion, 8)
  assert.equal(preview.groupVersion, 12)
  assert.equal(preview.schoolFields[0].value, '数控技术')
  assert.equal(preview.maskedContact, '138****0000')
  assert.equal(Object.hasOwn(preview, 'volunteers'), false)
})

test('A03 production seal distinguishes explicit v0 from missing preview concurrency evidence', () => {
  assert.equal(normalizeMaterialPreview({ profileVersion: 0, groupVersion: 0 }).profileVersion, 0)
  assert.equal(normalizeMaterialPreview({ profileVersion: 0, groupVersion: 0 }).groupVersion, 0)
  assert.equal(normalizeMaterialPreview({}).profileVersion, null)
  assert.equal(normalizeMaterialPreview({}).groupVersion, null)
})

test('A03-6 PDF preview is server-derived and explicitly excludes other volunteers', () => {
  assert.deepEqual(buildPdfPreviewRequest({
    previewHash: 'sha256:abc',
    contactSharingMode: 'AFTER_INTERVIEW'
  }), {
    materialPreviewHash: 'sha256:abc',
    contactSharingMode: 'AFTER_INTERVIEW',
    includeVolunteerApplications: false
  })
  assert.throws(() => buildPdfPreviewRequest({ contactSharingMode: 'AFTER_INTERVIEW' }), /先获取企业视角材料预览/)
})
