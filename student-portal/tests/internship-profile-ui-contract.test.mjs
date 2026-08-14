import test from 'node:test'
import assert from 'node:assert/strict'

import {
  SCHOOL_VERIFIED_FIELDS,
  STUDENT_EDITABLE_FIELDS,
  buildInternshipProfileUpdate,
  normalizeInternshipProfile,
  normalizeProfileCompleteness
} from '../src/modules/internshipRecruitment/profileModel.js'

test('A03-5 school canonical student facts remain read-only projection', () => {
  const profile = normalizeInternshipProfile({
    version: 8,
    schoolFacts: {
      name: '张同学', studentNo: '202401001', college: '智能制造学院', major: '数控技术', grade: '2024级', className: '数控2401'
    },
    selfIntroduction: '认真负责',
    strengths: '设备操作',
    skillTags: ['CAD']
  })
  assert.deepEqual(Object.keys(profile.school), SCHOOL_VERIFIED_FIELDS)
  assert.equal(profile.school.studentNo, '202401001')
})

test('A03-5 update payload only contains student-editable fields plus optimistic version', () => {
  const payload = buildInternshipProfileUpdate({
    version: 8,
    school: { name: '篡改姓名', studentNo: '篡改学号', college: '篡改学院', major: '篡改专业', grade: '篡改年级', className: '篡改班级' },
    selfIntroduction: '  自我介绍  ',
    strengths: '  我的优势  ',
    skillTags: [' CAD ', 'PLC'],
    availableFrom: '2026-09-01',
    locationPreferences: [' 长沙 ', '株洲']
  })
  assert.deepEqual(Object.keys(payload), ['expectedVersion', ...STUDENT_EDITABLE_FIELDS])
  assert.equal(payload.expectedVersion, 8)
  assert.equal(payload.selfIntroduction, '自我介绍')
  assert.deepEqual(payload.skillTags, ['CAD', 'PLC'])
  for (const forbidden of SCHOOL_VERIFIED_FIELDS) assert.equal(Object.hasOwn(payload, forbidden), false)
})

test('A03-5 completeness keeps backend blockers and submit conclusion', () => {
  assert.deepEqual(normalizeProfileCompleteness({ percent: 80, blockers: [{ code: 'INTRO_REQUIRED', message: '请补充自我介绍' }], canSubmit: false }), {
    percent: 80,
    blockers: [{ code: 'INTRO_REQUIRED', message: '请补充自我介绍' }],
    ready: false
  })
})
