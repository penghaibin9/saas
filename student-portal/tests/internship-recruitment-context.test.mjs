import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  formatDeadline,
  normalizeRecruitmentContext,
  selectionConclusion
} from '../src/modules/internshipRecruitment/contextModel.js'

const apiSource = readFileSync(new URL('../src/services/internshipSelectionApi.js', import.meta.url), 'utf8')

test('A03-1 maps recruitment context without inventing client truth', () => {
  const context = normalizeRecruitmentContext({
    campaign: { id: 9, name: '2026 秋季岗位实习双选', status: 'OPEN', studentSelectionEndAt: '2026-09-10T18:00:00+08:00' },
    stats: { publishedPositions: 128, partnerCompanies: 46, matchedPositions: 31 },
    volunteerGroup: { status: 'DRAFT', selectedCount: 2 }
  })
  assert.equal(context.campaignId, 9)
  assert.equal(context.phaseLabel, '选岗进行中')
  assert.equal(context.publishedPositions, 128)
  assert.equal(context.partnerCompanies, 46)
  assert.equal(context.matchedPositions, 31)
  assert.equal(context.selectedVolunteers, 2)
  assert.equal(context.canSelect, true)
  assert.match(selectionConclusion(context), /已选 2\/3 个志愿/)
})

test('A03-1 LOCKED explains accept intent and school confirmation deadline', () => {
  const context = normalizeRecruitmentContext({
    campaignStatus: 'OPEN',
    volunteerStatus: 'LOCKED',
    lockedCompanyName: '中联重科',
    teacherConfirmDeadline: '2026-09-12T12:00:00+08:00',
    canSelect: false
  })
  assert.equal(context.groupStatusLabel, '等待学校最终确认')
  assert.match(selectionConclusion(context), /中联重科 已拟接收/)
  assert.notEqual(formatDeadline(context.schoolConfirmDeadline), '待学校公布')
})

test('A03-1 NEEDS_REVISION explicitly restores editing conclusion', () => {
  const context = normalizeRecruitmentContext({ campaignStatus: 'OPEN', volunteerStatus: 'NEEDS_REVISION', canSelect: true })
  assert.equal(selectionConclusion(context), '本轮可重新调整志愿')
})

test('A03-11 canonical APPROVED context is final even while campaign is still open', () => {
  const context = normalizeRecruitmentContext({
    campaignStatus: 'OPEN', volunteerStatus: 'APPROVED', selectedVolunteerCount: 3, canSelect: true
  })
  assert.equal(context.groupStatusLabel, '学校已确认')
  assert.match(selectionConclusion(context), /学校已完成最终确认/)
  assert.doesNotMatch(selectionConclusion(context), /可继续调整/)
})

test('A03 production seal makes context reads latest-wins and authority failures browse-only', () => {
  const unavailable = normalizeRecruitmentContext({
    campaignStatus: 'UNAVAILABLE',
    phaseLabel: '招聘季信息暂不可用',
    canSelect: false,
    selectionBlockReason: '暂时无法读取学校招聘季信息，请重新加载后再调整志愿。'
  })
  assert.equal(unavailable.canSelect, false)
  assert.match(selectionConclusion(unavailable), /暂时无法读取学校招聘季信息/)
  assert.match(apiSource, /function latestRead\(/)
  assert.match(apiSource, /context\(\) \{ return latestRead\('context'/)
  assert.match(apiSource, /canSelect: false/)
  assert.match(apiSource, /selectionBlockReason/)
})
