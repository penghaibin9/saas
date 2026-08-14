import test from 'node:test'
import assert from 'node:assert/strict'

import { conditionRows, normalizePosition } from '../src/modules/internshipRecruitment/positionModel.js'

test('A03-3 position card only exposes frozen backend match states', () => {
  assert.equal(normalizePosition({ matchState: 'MATCHED' }).matchLabel, '专业匹配')
  assert.equal(normalizePosition({ matchState: 'UNLIMITED' }).matchLabel, '不限专业')
  assert.equal(normalizePosition({ matchState: 'POSSIBLE_MISMATCH' }).matchLabel, '可能不匹配')
  assert.equal(normalizePosition({ matchState: 'AI_96_PERCENT' }).matchState, 'UNKNOWN')
})

test('A03-3 detail keeps labor conditions in explicit first-class rows', () => {
  const position = normalizePosition({
    dailyHours: 8,
    weeklyHours: 40,
    shift: '白班',
    nightShift: false,
    overtimePolicy: '原则上不安排',
    restDays: '双休',
    remunerationDisplay: '3000-3500 元/月',
    subsidyDisplay: '餐补 20 元/天',
    accommodationProvided: true,
    mealProvided: true,
    hazardousExposure: '机械加工噪声',
    protectiveEquipment: '护目镜、防护鞋'
  })
  const rows = Object.fromEntries(conditionRows(position))
  assert.equal(rows['每日工时'], 8)
  assert.equal(rows['每周工时'], 40)
  assert.equal(rows['夜班'], '无')
  assert.equal(rows['岗位薪酬'], '3000-3500 元/月')
  assert.equal(rows['住宿'], '提供')
  assert.equal(rows['餐食'], '提供')
  assert.equal(rows['危险因素'], '机械加工噪声')
  assert.equal(rows['劳动防护/设备'], '护目镜、防护鞋')
})

test('A03-3 normalizes card skeleton from server DTO without client scoring', () => {
  const position = normalizePosition({
    id: 201,
    title: '数控加工实习生',
    salaryRange: '3200-3800 元/月',
    company: { id: 18, name: '湖湘智能制造有限公司', schoolVerified: true },
    workLocation: '长沙市',
    majors: ['数控技术', '机电一体化'],
    grades: ['2024级'],
    remaining: 6,
    publishedAt: '2026-08-10T08:00:00+08:00',
    matchState: 'MATCHED'
  })
  assert.equal(position.id, 201)
  assert.equal(position.companyId, 18)
  assert.equal(position.companyVerified, true)
  assert.equal(position.remaining, 6)
  assert.equal(position.matchState, 'MATCHED')
})
