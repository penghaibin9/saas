import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const employment = readFileSync(new URL('../src/views/employment/EmploymentView.vue', import.meta.url), 'utf8')
const academic = readFileSync(new URL('../src/views/academic/AcademicView.vue', import.meta.url), 'utf8')

test('就业回访表绑定真实 DTO 并把跟进方式业务化', () => {
  const block = employment.match(/const FOLLOW_UP_COLS = \[[\s\S]*?\n\]/)?.[0] || ''
  assert.match(block, /key: 'time'/)
  assert.match(block, /key: 'way'/)
  assert.match(block, /key: 'content'/)
  assert.doesNotMatch(block, /followUpAt|contactType|result|note/)
  assert.match(employment, /PHONE: '电话联系'/)
})

test('专业分流表只使用真实志愿 DTO 且不展示数据库 ID', () => {
  const block = academic.match(/const SPLIT_COLS = \[[\s\S]*?\n\]/)?.[0] || ''
  assert.match(block, /key: 'choices'/)
  assert.match(block, /key: 'gpa'/)
  assert.match(block, /key: 'resultChoiceRank'/)
  assert.match(block, /key: 'adjustReason'/)
  assert.doesNotMatch(block, /batchName|choiceOrder|majorName|resultMajorName/)
  assert.doesNotMatch(block, /key: 'resultMajorId'/)
})

test('就业签约材料表绑定真实 DTO，不制造不存在字段', () => {
  const block = employment.match(/const MATERIAL_COLS = \[[\s\S]*?\n\]/)?.[0] || ''
  assert.match(block, /key: 'type'/)
  assert.match(block, /key: 'fileName'/)
  assert.match(block, /key: 'status'/)
  assert.doesNotMatch(block, /materialType|uploadedAt|reviewNote/)
})
