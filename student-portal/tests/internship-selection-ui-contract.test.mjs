import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  CATALOG_MAX_PAGE_SIZE,
  CATALOG_PAGE_SIZE,
  INTERNSHIP_SELECTION_ROUTE,
  INTERNSHIP_SELECTION_TITLE,
  POSITION_CARD_LAYOUT,
  POSITION_MATCH_STATES,
  SELECTION_BREAKPOINTS,
  buildVolunteerDraftPayload,
  buildVolunteerSubmitPayload,
  normalizeCatalogQuery
} from '../src/modules/internshipRecruitment/selectionContract.js'

const selectionViewSource = readFileSync(new URL('../src/views/internship/InternshipSelectionView.vue', import.meta.url), 'utf8')

test('A03-0 freezes student selection naming, route and responsive layout', () => {
  assert.equal(INTERNSHIP_SELECTION_TITLE, '实习选岗')
  assert.equal(INTERNSHIP_SELECTION_ROUTE, '/internship/selection')
  assert.deepEqual(SELECTION_BREAKPOINTS, { threeColumn: 1440, floatingVolunteer: 1100, singleColumn: 900 })
  assert.equal(POSITION_CARD_LAYOUT.title.fontSize, 18)
  assert.equal(POSITION_CARD_LAYOUT.title.color, '#1a1a1a')
  assert.equal(POSITION_CARD_LAYOUT.remuneration.fontSize, 16)
  assert.equal(POSITION_CARD_LAYOUT.remuneration.color, '#fa541c')
  assert.equal(POSITION_CARD_LAYOUT.tag.background, '#f0f5ff')
  assert.equal(POSITION_CARD_LAYOUT.tag.radius, 4)
})

test('A03-0 catalog query is always server-paged and bounded', () => {
  assert.equal(CATALOG_PAGE_SIZE, 20)
  assert.equal(CATALOG_MAX_PAGE_SIZE, 100)
  assert.deepEqual(normalizeCatalogQuery({ page: -9, pageSize: 999, keyword: '数控', city: '长沙' }), {
    page: 1,
    pageSize: 100,
    sort: 'RECOMMENDED',
    keyword: '数控',
    city: '长沙'
  })
})

test('A03-0 matching states stay backend-contract only', () => {
  assert.deepEqual(POSITION_MATCH_STATES, ['MATCHED', 'UNLIMITED', 'UNKNOWN', 'POSSIBLE_MISMATCH'])
  assert.equal(POSITION_MATCH_STATES.some((value) => value.includes('%')), false)
})

test('A03-0 volunteer draft is one fixed-slot group payload with group version token', () => {
  const payload = buildVolunteerDraftPayload({
    batchId: 8,
    internshipId: 901,
    expectedGroupVersion: 12,
    expectedRecordVersion: 7,
    expectedApplicationVersions: { 1: 2, 2: 1, 3: 0 },
    items: [
      { volunteerNo: 1, positionId: 201, applicationStatement: '希望参与数控加工实习' },
      { volunteerNo: 2, positionId: 203, applicationStatement: '希望提升设备维护能力' }
    ]
  })
  assert.equal(payload.items.length, 2)
  assert.equal(payload.items[0].volunteerNo, 1)
  assert.equal(payload.items[1].volunteerNo, 2)
  assert.equal(payload.expectedGroupVersion, 12)
  assert.throws(() => buildVolunteerDraftPayload({ expectedGroupVersion: 1, items: [
    { volunteerNo: 1, positionId: 201 },
    { volunteerNo: 2, positionId: 201 }
  ] }), /不能重复/)
  assert.throws(() => buildVolunteerDraftPayload({ items: [{ volunteerNo: 1, positionId: 201 }] }), /志愿组版本缺失/)
})

test('A03-0 submit requires preview hash, explicit contact policy and versions', () => {
  assert.deepEqual(buildVolunteerSubmitPayload({
    expectedGroupVersion: 12,
    expectedProfileVersion: 8,
    consentPolicyVersion: 'INTERN_APPLICATION_PRIVACY_2026_08',
    confirmMaterialPreviewHash: 'sha256:abc'
  }), {
    expectedGroupVersion: 12,
    expectedProfileVersion: 8,
    consentPolicyVersion: 'INTERN_APPLICATION_PRIVACY_2026_08',
    contactSharingMode: 'AFTER_INTERVIEW',
    confirmMaterialPreviewHash: 'sha256:abc'
  })
  assert.throws(() => buildVolunteerSubmitPayload({ expectedGroupVersion: 12, expectedProfileVersion: 8, consentPolicyVersion: 'v1' }), /必须确认/)
  assert.throws(() => buildVolunteerSubmitPayload({ expectedProfileVersion: 8, consentPolicyVersion: 'v1', confirmMaterialPreviewHash: 'sha256:x' }), /志愿组版本缺失/)
  assert.throws(() => buildVolunteerSubmitPayload({ expectedGroupVersion: 12, consentPolicyVersion: 'v1', confirmMaterialPreviewHash: 'sha256:x' }), /实习档案版本缺失/)
  assert.equal(buildVolunteerSubmitPayload({
    expectedGroupVersion: 0,
    expectedProfileVersion: 0,
    consentPolicyVersion: 'v1',
    confirmMaterialPreviewHash: 'sha256:x'
  }).expectedProfileVersion, 0)
})

test('A03-11 student-facing selection fails closed when volunteer authority is unavailable', () => {
  assert.match(selectionViewSource, /normalizeVolunteerGroup\(\{ status: 'UNAVAILABLE' \}\)/)
  assert.match(selectionViewSource, /系统不会用本地数据替代学校记录/)
  assert.match(selectionViewSource, /if \(!volunteerEditable\.value \|\| submissionBusy\.value\)/)
  assert.match(selectionViewSource, /if \(!submissionConfirmed\.value \|\| !volunteerEditable\.value \|\| submissionBusy\.value\) return/)
  assert.doesNotMatch(selectionViewSource, /A01 接口就绪后/)
})
