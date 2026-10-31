import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { INTERNSHIP_TAB_GROUPS } from '../src/modules/internshipRecruitment/navigation.js'

const source = readFileSync(new URL('../src/views/internship/InternshipView.vue', import.meta.url), 'utf8')

const expectedTabs = [
  'overview', 'plan', 'insurance', 'agreement',
  'enterprises', 'intention', 'application',
  'checkin', 'makeup', 'leave', 'report',
  'change', 'help', 'eval',
]

test('V8 student internship workbench groups every legacy capability exactly once', () => {
  const grouped = INTERNSHIP_TAB_GROUPS.flatMap(group => group.tabs.map(item => item.key))
  for (const key of expectedTabs) assert.ok(grouped.includes(key === 'enterprises' ? 'selection' : key))
  for (const key of ['notices','consent','materials','profile','safety']) assert.ok(grouped.includes(key))
  assert.equal(new Set(grouped).size, grouped.length)
  assert.equal(source.includes('v-for="t in tabs"'), false)
  assert.deepEqual(INTERNSHIP_TAB_GROUPS.map(group=>group.label), ['安排与入岗','选岗与申请','在岗办理','变更与结果'])
  assert.match(source, /v-for="group in tabGroups"/)
})

test('V8 student internship workbench puts Now Action before grouped navigation and content', () => {
  const now = source.indexOf('class="sp-card sp-now"')
  const groups = source.indexOf('class="sp-process-nav"')
  const content = source.indexOf('<!-- 我的实习 -->')

  assert.ok(now >= 0)
  assert.ok(groups > now)
  assert.ok(content > groups)
  assert.match(source, /最近变化：\{\{ currentAction\.recentChange \}\}/)
  assert.match(source, /完成后：\{\{ currentAction\.nextActor \}\}/)
})

test('V8 student internship deep links preserve all original fourteen views', () => {
  for (const key of expectedTabs) {
    assert.match(source, new RegExp(`tab === '${key}'`))
  }
  assert.match(source, /router\.replace\(\{ query: \{ \.\.\.route\.query, view: key \} \}\)/)
  assert.match(source, /watch\(\(\) => route\.query\.view/)
})

test('V8 student internship routes the visible catalog entry to canonical volunteer selection', () => {
  assert.match(source, /enterprises:'\/internship\/selection',selection:'\/internship\/selection'/)
  assert.match(source, /router\.push\(\{path,query:my\.value\.batchId/)
})

test('V8 change workbench loads its target position authority without a prior catalog visit', () => {
  const changeSource = source.split("if (key === 'change') {", 2)[1].split("if (key === 'report') {", 1)[0]
  assert.match(changeSource, /Promise\.all/)
  assert.match(changeSource, /loadChanges\(1\)/)
  assert.match(changeSource, /loadChangeTargets\(1\)/)
  assert.match(source, /internshipCoreApi\.changes\(ctx, page\)/)
  assert.match(source, /internshipCoreApi\.changeTargets\(ctx, type, keyword, page\)/)
})

test('V8 student internship sources are lazy, local-stateful, and retryable', () => {
  for (const state of ['idle', 'loading', 'data', 'empty', 'error']) {
    assert.match(source, new RegExp(`'${state}'`))
  }
  assert.match(source, /retryCurrentSource/)
  assert.match(source, /loadTab\(tab\.value, true\)/)
  assert.match(source, /new Set\(\['agreement', 'insurance', 'plan', 'report', 'checkin', tab\.value]\)/)
  assert.equal(source.includes('loadExtras'), false)
  assert.equal(source.includes('catch { enterprises.value = [] }'), false)
  assert.equal(source.includes('catch { agreements.value = []; activeAgreement.value = null }'), false)
})
