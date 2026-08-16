import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  addMobileVolunteer,
  buildMobileVolunteerSaveRequest,
  buildMobileVolunteerSubmitRequest,
  canEditMobileVolunteers,
  mobileConditionRows,
  moveMobileVolunteer,
  normalizeMobileMaterialPreview,
  normalizeMobilePositionDetail,
  normalizeMobileVolunteerGroup,
  updateMobileStatement
} from '../src/modules/internshipVolunteerModel.js'

const pageSource = readFileSync(new URL('../src/pages/student/internship/enterprises/index.vue', import.meta.url), 'utf8')

test('A03-10 detail exposes all school internship labor conditions above fixed safe action bar', () => {
  const position = normalizeMobilePositionDetail({
    id: 201, title: '数控加工实习生', remunerationDisplay: '3200 元/月', dailyHours: 8, weeklyHours: 40, shift: '白班', nightShift: false,
    overtimePolicy: '原则上不安排', restDays: '双休', subsidyDisplay: '餐补', accommodationProvided: true, mealProvided: true,
    hazardousExposure: '机械加工噪声', protectiveEquipment: '护目镜、防护鞋'
  })
  const rows = Object.fromEntries(mobileConditionRows(position))
  for (const key of ['每日工时','每周工时','班次','夜班','加班安排','休息日','岗位薪酬','补贴','住宿','餐食','危险因素','劳动防护/设备']) assert.ok(Object.hasOwn(rows, key), `missing ${key}`)
  assert.match(pageSource, /MobileSafeAreaBar v-if="mode === 'detail'"/)
  assert.match(pageSource, /剩余名额/)
  assert.match(pageSource, /加入志愿/)
})

test('A03-10 mobile volunteers are fixed slots and use up/down, never drag', () => {
  const group = normalizeMobileVolunteerGroup({ status: 'DRAFT', version: 12, batchId: 8, internshipId: 901, recordVersion: 7,
    items: [{ volunteerNo: 1, positionId: 201, positionName: '岗位A', version: 2 }, { volunteerNo: 2, positionId: 203, positionName: '岗位B', version: 1 }] })
  assert.deepEqual(group.slots.map((slot) => slot.volunteerNo), [1,2,3])
  assert.equal(canEditMobileVolunteers(group), true)
  assert.equal(canEditMobileVolunteers({ status: 'LOCKED' }), false)
  const added = addMobileVolunteer(group.slots, { id: 218, title: '岗位C', companyName: '企业C' })
  const moved = moveMobileVolunteer(added, 3, 'UP')
  assert.deepEqual(moved.map((slot) => slot.positionId), [201,218,203])
  assert.match(pageSource, />上移</)
  assert.match(pageSource, />下移</)
  assert.doesNotMatch(pageSource, /drag|draggable/i)
})

test('A03-10 each volunteer keeps its own statement and all slots save with three-layer CAS', () => {
  const group = normalizeMobileVolunteerGroup({ status:'DRAFT', version:12, batchId:8, internshipId:901, recordVersion:7,
    items:[{volunteerNo:1,positionId:201,version:2},{volunteerNo:2,positionId:203,version:1}] })
  const slots = updateMobileStatement(addMobileVolunteer(group.slots, { id:218,title:'岗位C' }), 3, '申请岗位C的独立说明')
  const payload = buildMobileVolunteerSaveRequest(group, slots)
  assert.equal(payload.items.length, 3)
  assert.equal(payload.items[2].applicationStatement, '申请岗位C的独立说明')
  assert.equal(payload.expectedGroupVersion, 12)
  assert.equal(payload.expectedRecordVersion, 7)
  assert.deepEqual(payload.expectedApplicationVersions, {'1':2,'2':1,'3':0})
  assert.throws(() => buildMobileVolunteerSaveRequest({ ...group, version: null }, slots), /志愿组版本缺失/)
  assert.throws(() => buildMobileVolunteerSaveRequest({ ...group, recordVersion: null }, slots), /实习记录版本缺失/)
  const missingApplicationVersion = slots.map((slot) => slot.volunteerNo === 1 ? { ...slot, version: null } : slot)
  assert.throws(() => buildMobileVolunteerSaveRequest(group, missingApplicationVersion), /第1志愿版本缺失/)
})

test('A03 production privacy seal defaults mobile submit and UI to MASKED_ONLY', () => {
  const group = normalizeMobileVolunteerGroup({ status:'DRAFT', version:12 })
  const preview = normalizeMobileMaterialPreview({ previewHash:'sha256:abc', consentPolicyVersion:'INTERN_APPLICATION_PRIVACY_2026_08', profileVersion:8 })
  assert.deepEqual(buildMobileVolunteerSubmitRequest(group, preview), {
    expectedGroupVersion:12, expectedProfileVersion:8, consentPolicyVersion:'INTERN_APPLICATION_PRIVACY_2026_08',
    contactSharingMode:'MASKED_ONLY', confirmMaterialPreviewHash:'sha256:abc'
  })
  assert.equal(buildMobileVolunteerSubmitRequest(group, preview, 'AFTER_INTERVIEW').contactSharingMode, 'AFTER_INTERVIEW')
  assert.match(pageSource, /contactMode: 'MASKED_ONLY'/)
  assert.match(pageSource, /contactIndex\(\).*index >= 0 \? index : 0/)
  assert.match(pageSource, /changeContactMode\(e\).*\|\| 'MASKED_ONLY'/)
  assert.throws(() => buildMobileVolunteerSubmitRequest({ ...group, version: null }, preview), /志愿组版本缺失/)
  const missingProfileVersion = normalizeMobileMaterialPreview({ previewHash:'sha256:abc', consentPolicyVersion:'INTERN_APPLICATION_PRIVACY_2026_08' })
  assert.equal(missingProfileVersion.profileVersion, null)
  assert.throws(() => buildMobileVolunteerSubmitRequest(group, missingProfileVersion), /实习档案版本缺失/)
})

test('A03-10 LOCKED UX explains school confirmation and only offers unlock request', () => {
  assert.match(pageSource, /志愿已锁定/)
  assert.match(pageSource, /已拟接收，等待学校最终确认/)
  assert.match(pageSource, /申请改志愿/)
  assert.match(pageSource, /requestUnlock/)
})

test('A03-11 canonical APPROVED is final and cannot reopen mobile submission', () => {
  const group = normalizeMobileVolunteerGroup({ status: 'APPROVED', version: 13 })
  assert.equal(group.status, 'APPROVED')
  assert.equal(canEditMobileVolunteers(group), false)
  assert.match(pageSource, /APPROVED: '学校已确认'/)
  assert.match(pageSource, /v-else-if="volunteerFinalized"[^>]*disabled>学校已确认<\/button>/)
  assert.match(pageSource, /!volunteerEditable \|\| activeSlots\.length < 1/)
})

test('A03-11 unavailable volunteer authority fails closed on mobile', () => {
  const group = normalizeMobileVolunteerGroup()
  assert.equal(group.status, 'UNAVAILABLE')
  assert.equal(group.version, null)
  assert.equal(canEditMobileVolunteers(group), false)
  assert.match(pageSource, /volunteerState === 'ready' && canEditMobileVolunteers/)
  assert.match(pageSource, /normalizeMobileVolunteerGroup\(\{ status: 'UNAVAILABLE' \}\)/)
  assert.match(pageSource, /UNAVAILABLE: '暂不可用'/)
  assert.match(pageSource, /系统不会用本地数据替代学校记录/)
})

test('A03-11 unknown recruitment context is browse-only and never writable', () => {
  assert.match(pageSource, /Boolean\(this\.context && this\.context\.canSelect\)/)
  assert.doesNotMatch(pageSource, /&& \(!this\.context \|\| this\.context\.canSelect\)/)
})
