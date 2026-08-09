import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  HELP_V3_CORE_JOURNEYS,
  HELP_V3_HOME_INTENTS,
  HELP_V3_QUICK_QUESTIONS
} from '../help/helpCenterV3.js'
import { matchesHelpSearchText, tokenizeHelpQuery } from '../help/helpSearch.js'

const here = dirname(fileURLToPath(import.meta.url))
const modelSource = readFileSync(resolve(here, '../helpCenterModel.js'), 'utf8')
const viewSource = readFileSync(resolve(here, '../../views/admin/help/AdminHelpView.vue'), 'utf8')

test('V3 home is organized around tasks, problems and core journeys', () => {
  assert.deepEqual(HELP_V3_HOME_INTENTS.map((item) => item.key), ['tasks', 'problems', 'journeys'])
  assert.match(HELP_V3_HOME_INTENTS[0].title, /办一件事/)
  assert.match(HELP_V3_HOME_INTENTS[1].title, /遇到问题/)
  assert.match(HELP_V3_HOME_INTENTS[2].title, /核心业务流程/)
  assert.ok(HELP_V3_QUICK_QUESTIONS.length >= 8)
})

test('V3 core journey registry covers the four commercial domains without reviving legacy help ids', () => {
  assert.deepEqual(HELP_V3_CORE_JOURNEYS.map((item) => item.key), [
    'academic',
    'internship',
    'graduation',
    'student-affairs'
  ])
  const ids = HELP_V3_CORE_JOURNEYS.flatMap((item) => item.helpIds)
  for (const id of [
    'aa-card-grade-review-publish',
    'in-v2-student-application',
    'in-v2-score',
    'gd-v2-topic-selection',
    'gd-v2-grade',
    'sa-card-risk-handle',
    'sa-card-archive'
  ]) {
    assert.ok(ids.includes(id), `${id} should be part of a V3 verified journey`)
  }
  assert.ok(!ids.includes('in-card-eval-score'))
  assert.ok(!ids.includes('gd-card-defense-grade'))
})

test('V3 model resolves journey nodes only through published help entries and role visibility', () => {
  assert.match(modelSource, /export function getV3CoreJourneys/)
  assert.match(modelSource, /journey\.helpIds\.map\(getHelpEntry\)\.filter\(Boolean\)/)
  assert.match(modelSource, /isHelpVisibleForRole\(entry\.item, role\)/)
  assert.match(modelSource, /export function getV3HomeModel/)
  assert.match(modelSource, /matchesHelpSearchText\(entry\.searchText, q\)/)
})

test('question-style search tokenizes Chinese natural language and mixed error codes', () => {
  const tokens = tokenizeHelpQuery('为什么成绩提交不了 409')
  for (const token of ['成绩', '提交', '409']) assert.ok(tokens.includes(token), `${token} should be searchable`)
  assert.ok(!tokens.includes('为什么'))
  assert.ok(!tokens.includes('不了'))

  const corpus = '成绩录入 提交 发布 版本冲突 409 错误处理'
  assert.equal(matchesHelpSearchText(corpus, '为什么成绩提交不了'), true)
  assert.equal(matchesHelpSearchText(corpus, '成绩 409'), true)
  assert.equal(matchesHelpSearchText(corpus, '实习 409'), false)
})

test('V3 page leads with self-service intents and supports next-step and escalation guidance', () => {
  for (const text of [
    '免培训自助服务',
    '我要办一件事',
    '我遇到问题',
    '核心业务流程',
    '做不了时怎么自己排查',
    '办完以后下一步',
    '什么情况才需要找管理员'
  ]) {
    assert.match(viewSource, new RegExp(text))
  }
  assert.match(viewSource, /applyQuickQuestion/)
  assert.match(viewSource, /getV3HomeModel/)
  assert.match(viewSource, /verified-only/)
})
