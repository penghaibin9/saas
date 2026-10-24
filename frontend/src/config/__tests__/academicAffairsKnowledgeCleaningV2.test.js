import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from '../help/academicAffairsCleanHelpCards.js'
import { buildHelpSearchText } from '../helpCenterCore.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')

const EXPECTED_IDS = [
  'aa-card-status-change',
  'aa-card-grade-entry',
  'aa-card-grade-review-publish',
  'aa-card-grade-change',
  'aa-card-selection-round',
  'aa-card-selection-publish',
  'aa-card-exam-arrangement',
  'aa-card-exam-publish'
]

function card(id) {
  const found = ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS.find((item) => item.id === id)
  assert.ok(found, id)
  return found
}

function text(id) {
  return buildHelpSearchText(card(id))
}

test('academic V2 publishes one clean authoritative set for status grade selection and exam', () => {
  assert.deepEqual(ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS.map((item) => item.id), EXPECTED_IDS)
  assert.equal(new Set(EXPECTED_IDS).size, EXPECTED_IDS.length)
  assert.match(runtimeSource, /ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS\)/)
  assert.match(runtimeSource, /ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS\.map/)
  assert.doesNotMatch(runtimeSource, /applyCardOverrides\(cardsById, ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES\)/)
  assert.doesNotMatch(runtimeSource, /Object\.keys\(ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES\)/)
})

test('all cleaned academic cards satisfy the V2 seven-dimensional task contract', () => {
  for (const item of ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS) {
    assert.ok(item.title, item.id)
    assert.ok(item.summary, item.id)
    assert.ok(Array.isArray(item.keywords) && item.keywords.length > 0, item.id)
    assert.ok(Array.isArray(item.roles) && item.roles.length > 0, item.id)
    assert.ok(item.entry, item.id)
    assert.match(item.route, /^\/admin\/academic-affairs\//, item.id)
    assert.ok(Array.isArray(item.prerequisites) && item.prerequisites.length > 0, item.id)
    assert.ok(Array.isArray(item.permissions) && item.permissions.length > 0, item.id)
    assert.ok(Array.isArray(item.steps) && item.steps.length >= 3, item.id)
    assert.ok(Array.isArray(item.successCriteria) && item.successCriteria.length > 0, item.id)
    assert.ok(Array.isArray(item.troubleshooting) && item.troubleshooting.length > 0, item.id)
  }
})

test('student-status guide keeps real change types, approval nodes, scopes and configurable suspension limit', () => {
  const value = text('aa-card-status-change')
  assert.match(value, /学校可在规则中心调整上限/)
  assert.match(value, /复学/)
  assert.match(value, /退学/)
  assert.match(value, /转专业/)
  assert.match(value, /转班/)
  assert.match(value, /preserve/)
  assert.match(value, /retain/)
  assert.match(value, /辅导员→学院→教务处/)
  assert.match(value, /转出学院和转入学院/)
  assert.match(value, /休学期限/)
  assert.match(value, /学校可在规则中心调整上限/)
  assert.match(value, /academicaffairs\.statuschange\.counselorreview/)
  assert.match(value, /学院审核需要“学院审核”权限/)
  assert.match(value, /academicaffairs\.statuschange\.officereview/)
  assert.doesNotMatch(value, /休学到期日：休学默认2年/)
})

test('grade entry guide uses dynamic components and never restores the fixed usual-final formula', () => {
  const value = text('aa-card-grade-entry')
  assert.match(value, /1–12 个成绩项/)
  assert.match(value, /严格合计 100/)
  assert.match(value, /未开始、录入中、已退回时/)
  assert.match(value, /录入中/)
  assert.match(value, /returned/)
  assert.match(value, /absent/)
  assert.match(value, /deferred/)
  assert.match(value, /exempt/)
  assert.match(value, /cheat/)
  assert.match(value, /特殊状态不是普通 0 分/)
  assert.doesNotMatch(value, /总评\s*=\s*平时分.*期末分/)
})

test('grade publish guide keeps publish transaction separate from the post-commit warning scan', () => {
  const value = text('aa-card-grade-review-publish')
  assert.match(value, /锁定正式教学名单/)
  assert.match(value, /“教务终审”环节/)
  assert.match(value, /published/)
  assert.match(value, /正式成绩/)
  assert.match(value, /预警扫描成功/)
  assert.match(value, /预警扫描失败/)
  assert.match(value, /扫描失败不会撤回已发布的成绩/)
  assert.match(value, /不要对已发布的成绩再次发布/)
})

test('grade correction guide preserves published-only, reason, approval and append-only version semantics', () => {
  const value = text('aa-card-grade-change')
  assert.match(value, /只有已发布的成绩可以发起正式更正/)
  assert.match(value, /不少于 5 个字/)
  assert.match(value, /学院和教务终审/)
  assert.match(value, /academicgrade/)
  assert.match(value, /superseded/)
  assert.match(value, /active/)
  assert.match(value, /不覆盖当前正式成绩/)
  assert.match(value, /409/)
})

test('selection round guide preserves one-open-round, lottery draw-once and server-capacity truth', () => {
  const value = text('aa-card-selection-round')
  assert.match(value, /fcfs/)
  assert.match(value, /lottery/)
  assert.match(value, /同一批次同一时间只能开放一个轮次/)
  assert.match(value, /closed/)
  assert.match(value, /drawn/)
  assert.match(value, /待抽签/)
  assert.match(value, /已选中/)
  assert.match(value, /未中签/)
  assert.match(value, /系统锁定后的名额/)
  assert.match(value, /志愿抽签\/投积分等未实现模式不能写入正式帮助/)
})

test('selection publish guide locks DRAFT publication and transactional enroll/drop rules', () => {
  const value = text('aa-card-selection-publish')
  assert.match(value, /只有草稿状态的选课批次可以发布/)
  assert.match(value, /至少有一门有效可选课程/)
  assert.match(value, /容量/)
  assert.match(value, /开班下限/)
  assert.match(value, /课程取消/)
  assert.match(value, /同一事务/)
  assert.match(value, /不会超出容量/)
})

test('exam arrangement guide publishes the real auto-exam engine without pretending it always succeeds', () => {
  const value = text('aa-card-exam-arrangement')
  assert.match(value, /“草稿 → 课程已确认 → 已编排 → 已发布 → 已结束 → 已归档”/)
  assert.match(value, /自动排考/)
  assert.match(value, /course_confirmed/)
  assert.match(value, /未定时间/)
  assert.match(value, /无花名册/)
  assert.match(value, /无可用教室/)
  assert.match(value, /教室容量不足/)
  assert.match(value, /人工编排不应被自动流程覆盖/)
  assert.doesNotMatch(value, /系统能自动排考吗？.*不能/)
})

test('exam publish guide requires rooms seats and invigilators before PUBLISHED', () => {
  const value = text('aa-card-exam-publish')
  assert.match(value, /“课程已确认”或“已编排”的/)
  assert.match(value, /考场、座位和至少 1 名监考/)
  assert.match(value, /阻止发布/)
  assert.match(value, /published/)
  assert.match(value, /archived/)
  assert.match(value, /只读/)
})
