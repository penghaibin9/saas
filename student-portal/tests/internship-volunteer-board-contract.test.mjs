import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  addVolunteer,
  buildVolunteerGroupSaveRequest,
  canEditVolunteerGroup,
  moveVolunteer,
  normalizeVolunteerGroup,
  removeVolunteer,
  replaceVolunteer,
  updateVolunteerStatement
} from '../src/modules/internshipRecruitment/volunteerModel.js'

const boardSource = readFileSync(new URL('../src/components/recruitment/VolunteerBoard.vue', import.meta.url), 'utf8')
const group = normalizeVolunteerGroup({
  status: 'DRAFT',
  batchId: 8,
  internshipId: 901,
  recordVersion: 7,
  items: [
    { volunteerNo: 1, positionId: 201, positionName: '数控加工', companyName: '企业A', version: 2 },
    { volunteerNo: 2, positionId: 203, positionName: '设备维护', companyName: '企业B', version: 1 }
  ]
})

test('A03-7 always exposes fixed first/second/third volunteer slots', () => {
  assert.deepEqual(group.slots.map((slot) => slot.volunteerNo), [1, 2, 3])
  assert.equal(group.slots[0].positionId, 201)
  assert.equal(group.slots[2].positionId, null)
  assert.equal(canEditVolunteerGroup(group), true)
  assert.equal(canEditVolunteerGroup({ status: 'LOCKED' }), false)
})

test('A03-7 add/replace/remove/move operate on one local group, never three API writes', () => {
  const added = addVolunteer(group.slots, { id: 218, title: '质量检测', companyName: '企业C' })
  assert.deepEqual(added.map((slot) => slot.positionId), [201, 203, 218])

  const moved = moveVolunteer(added, 3, 'UP')
  assert.deepEqual(moved.map((slot) => slot.positionId), [201, 218, 203])

  const replaced = replaceVolunteer(moved, 1, { id: 220, title: '工业机器人', companyName: '企业D' })
  assert.deepEqual(replaced.map((slot) => slot.positionId), [220, 218, 203])

  const removed = removeVolunteer(replaced, 2)
  assert.deepEqual(removed.map((slot) => slot.positionId), [220, 203, null])
})

test('A03-7 keeps an independent application statement per volunteer', () => {
  const updated = updateVolunteerStatement(group.slots, 2, '希望提升设备维护和故障诊断能力')
  assert.equal(updated[0].applicationStatement, '')
  assert.equal(updated[1].applicationStatement, '希望提升设备维护和故障诊断能力')
})

test('A03-7 builds exactly one atomic group PUT payload for all active slots', () => {
  const slots = addVolunteer(group.slots, { id: 218, title: '质量检测', companyName: '企业C' })
  const withStatement = updateVolunteerStatement(slots, 3, '希望锻炼质量管理能力')
  const payload = buildVolunteerGroupSaveRequest(group, withStatement)
  assert.equal(payload.items.length, 3)
  assert.deepEqual(payload.items.map((item) => item.volunteerNo), [1, 2, 3])
  assert.deepEqual(payload.items.map((item) => item.positionId), [201, 203, 218])
  assert.equal(payload.items[2].applicationStatement, '希望锻炼质量管理能力')
  assert.equal(payload.expectedRecordVersion, 7)
  assert.deepEqual(payload.expectedApplicationVersions, { '1': 2, '2': 1, '3': 0 })
})

test('A03-11 volunteer board labels canonical APPROVED as school-confirmed', () => {
  assert.match(boardSource, /APPROVED: '学校已确认'/)
  assert.match(boardSource, /CONFIRMED: '学校已确认'/)
  assert.equal(canEditVolunteerGroup({ status: 'APPROVED' }), false)
})
