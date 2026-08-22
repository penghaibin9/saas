import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const employment = readFileSync(new URL('../src/views/employment/EmploymentView.vue', import.meta.url), 'utf8')
const academic = readFileSync(new URL('../src/views/academic/AcademicView.vue', import.meta.url), 'utf8')

test('就业回访表绑定真实 DTO，跟进方式由服务端 canonical 字典业务化', () => {
  // V3 施工手册 SP-E10：业务字典必须由服务端 canonical 下发，前端不再本地维护。
  // 本用例原本断言页面里存在 `PHONE: '电话联系'` 这份本地字典——那正是要消除的
  // 反模式：本地副本会漏 code（新增跟进方式后前端直接显示英文原始码），且与
  // 管理端可能不是同一套。现在服务端在 DTO 上直接给 wayLabel。
  const block = employment.match(/const FOLLOW_UP_COLS = \[[\s\S]*?\n\]/)?.[0] || ''
  assert.match(block, /key: 'time'/)
  assert.match(block, /key: 'wayLabel'/)
  assert.match(block, /key: 'content'/)
  assert.doesNotMatch(block, /followUpAt|contactType|result|note/)
  // 页面不得再自带跟进方式业务字典
  assert.doesNotMatch(employment, /PHONE: '电话联系'/)
  assert.doesNotMatch(employment, /FOLLOW_UP_WAY/)
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

test('就业签约材料表绑定真实 DTO，材料类型与审核状态由服务端 canonical 字典业务化', () => {
  // SP-E10 同理：本地 MATERIAL_TYPE 字典只有 4 个 code，canonical L_MATTYPE 有 7 个
  // （漏掉 CONTRACT/ENLIST_PROOF/OTHER），漏掉的一律被归成"其他就业材料"——
  // 这是错误归类，不是"业务化"。审核状态同样：本地字典没有 SUBMITTED/REVIEWING/
  // RETURNED，界面会直接显示英文原始码。现在两者都由服务端下发 label。
  const block = employment.match(/const MATERIAL_COLS = \[[\s\S]*?\n\]/)?.[0] || ''
  assert.match(block, /key: 'typeLabel'/)
  assert.match(block, /key: 'fileName'/)
  assert.match(block, /key: 'statusLabel'/)
  assert.doesNotMatch(block, /uploadedAt|reviewNote/)
  // 页面不得再自带材料类型/审核状态业务字典
  assert.doesNotMatch(employment, /OFFER: '录用证明'/)
  assert.doesNotMatch(employment, /MATERIAL_TYPE = /)
  assert.doesNotMatch(employment, /const VERIFY = \{/)
  assert.doesNotMatch(employment, /const MAT = \{/)
})

test('就业页去向类型与状态字典全部来自服务端，前端不再硬编码业务枚举', () => {
  // SP-E03：学生 PC 曾硬编码 FURTHER/MILITARY，与 canonical FURTHER_STUDY/ENLISTED
  // 漂移，学生提交的去向管理端识别不了。现在选项由服务端下发。
  assert.match(employment, /employmentDestinationOptions/)
  assert.doesNotMatch(employment, /k: 'FURTHER'/)
  assert.doesNotMatch(employment, /k: 'MILITARY'/)
  assert.doesNotMatch(employment, /const DEST = \{/)
  // SP-E09：材料审核与去向核验是两个独立事实，页面必须分别展示
  assert.match(employment, /materialStatusLabel/)
  assert.match(employment, /verifyStatusLabel/)
})
