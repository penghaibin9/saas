import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  PROFILE_ITEM_TYPES,
  SCHOOL_VERIFIED_FIELDS,
  buildInternshipProfileUpdate,
  normalizeInternshipProfile,
  normalizeProfileCompleteness,
  normalizeProfileItems
} from '../src/modules/internshipRecruitment/profileModel.js'

const apiSource = readFileSync(new URL('../src/services/internshipSelectionApi.js', import.meta.url), 'utf8')

test('A03-5 school canonical student facts remain read-only projection', () => {
  const profile = normalizeInternshipProfile({
    schoolFacts: {
      realName: '张同学', studentNo: '202401001', collegeName: '智能制造学院', majorName: '数控技术', grade: '2024级', className: '数控2401'
    },
    profile: {
      profileVersion: 8,
      selfIntro: '认真负责',
      strengths: '设备操作',
      skillTags: ['CAD'],
      availableFrom: '2026-09-01',
      expectedLocations: ['长沙']
    }
  })
  assert.deepEqual(Object.keys(profile.school), SCHOOL_VERIFIED_FIELDS)
  assert.equal(profile.school.name, '张同学')
  assert.equal(profile.school.studentNo, '202401001')
  assert.equal(profile.version, 8)
  assert.equal(profile.selfIntroduction, '认真负责')
  assert.deepEqual(profile.locationPreferences, ['长沙'])
})

test('A03-5 update payload aligns A01 canonical profile service and excludes school facts', () => {
  const payload = buildInternshipProfileUpdate({
    version: 8,
    school: { name: '篡改姓名', studentNo: '篡改学号', college: '篡改学院', major: '篡改专业', grade: '篡改年级', className: '篡改班级' },
    selfIntroduction: '  自我介绍  ',
    strengths: '  我的优势  ',
    skillTags: [' CAD ', 'PLC'],
    availableFrom: '2026-09-01',
    locationPreferences: [' 长沙 ', '株洲']
  })
  assert.deepEqual(Object.keys(payload), ['expectedProfileVersion', 'selfIntro', 'strengths', 'skillTags', 'availableFrom', 'expectedLocations'])
  assert.equal(payload.expectedProfileVersion, 8)
  assert.equal(payload.selfIntro, '自我介绍')
  assert.deepEqual(payload.skillTags, ['CAD', 'PLC'])
  assert.deepEqual(payload.expectedLocations, ['长沙', '株洲'])
  for (const forbidden of SCHOOL_VERIFIED_FIELDS) assert.equal(Object.hasOwn(payload, forbidden), false)
})

test('A03-5 profile item types and projection align A01 canonical values', () => {
  assert.equal(PROFILE_ITEM_TYPES.some((item) => item.value === 'WORK'), false)
  assert.equal(PROFILE_ITEM_TYPES.some((item) => item.value === 'PORTFOLIO'), true)
  assert.equal(PROFILE_ITEM_TYPES.some((item) => item.value === 'SKILL_EVIDENCE'), true)
  const items = normalizeProfileItems({ items: [{ id: '3', itemType: 'PORTFOLIO', title: '数控作品', organization: '校内实训', startDate: '2026-03-01', fileIds: ['f1'] }] })
  assert.equal(items[0].type, 'PORTFOLIO')
  assert.equal(items[0].issuedBy, '校内实训')
  assert.equal(items[0].occurredAt, '2026-03-01')
  assert.equal(items[0].fileName, '1 个附件')
  assert.match(apiSource, /expectedProfileVersion/)
  assert.match(apiSource, /PORTFOLIO/)
  assert.match(apiSource, /expectedLocations/)
})

test('A03-5 completeness keeps backend blockers and submit conclusion', () => {
  assert.deepEqual(normalizeProfileCompleteness({ percent: 80, blockers: [{ code: 'INTRO_REQUIRED', message: '请补充自我介绍' }], canSubmit: false }), {
    percent: 80,
    blockers: [{ code: 'INTRO_REQUIRED', message: '请补充自我介绍' }],
    ready: false
  })
})
