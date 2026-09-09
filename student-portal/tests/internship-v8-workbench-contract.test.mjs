import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/internship/InternshipView.vue', import.meta.url), 'utf8')

const expectedTabs = [
  'overview', 'plan', 'insurance', 'agreement',
  'enterprises', 'intention', 'application',
  'checkin', 'makeup', 'leave', 'report',
  'change', 'help', 'eval',
]

test('V8 student internship workbench groups every legacy capability exactly once', () => {
  const grouped = [...source.matchAll(/tabs\.filter\(\(item\) => \[([^\]]+)]\.includes\(item\.key\)\)/g)]
    .flatMap((match) => [...match[1].matchAll(/'([^']+)'/g)].map((item) => item[1]))

  assert.deepEqual(grouped, expectedTabs)
  assert.equal(new Set(grouped).size, 14)
  assert.equal(source.includes('v-for="t in tabs"'), false)
  assert.match(source, /label: '安排与入岗'/)
  assert.match(source, /label: '选岗与申请'/)
  assert.match(source, /label: '在岗办理'/)
  assert.match(source, /label: '变更与结果'/)
})

test('V8 student internship workbench puts Now Action before grouped navigation and content', () => {
  const now = source.indexOf('class="sp-card sp-now"')
  const groups = source.indexOf('class="sp-process-nav"')
  const content = source.indexOf("tab === 'overview'")

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
  assert.match(source, /if \(key === 'enterprises'\) \{\s*router\.push\('\/internship\/selection'\)/)
})

test('V8 change workbench loads its target position authority without a prior catalog visit', () => {
  const changeSource = source.split("if (key === 'change') {", 2)[1].split("if (key === 'report') {", 1)[0]
  assert.match(changeSource, /Promise\.all/)
  assert.match(changeSource, /internshipCoreApi\.changes\(context\(\)\)/)
  assert.match(changeSource, /portalApi\.internshipEnterprises\(enterpriseCity\.value\)/)
  assert.match(changeSource, /enterprises\.value = rowsFrom\(positionRows\)/)
})

test('V8 student internship sources are lazy, local-stateful, and retryable', () => {
  for (const state of ['idle', 'loading', 'data', 'empty', 'error']) {
    assert.match(source, new RegExp(`'${state}'`))
  }
  assert.match(source, /retryCurrentSource/)
  assert.match(source, /loadTab\(tab\.value, true\)/)
  assert.match(source, /new Set\(\['agreement', 'insurance', 'plan', tab\.value]\)/)
  assert.equal(source.includes('loadExtras'), false)
  assert.equal(source.includes('catch { enterprises.value = [] }'), false)
  assert.equal(source.includes('catch { agreements.value = []; activeAgreement.value = null }'), false)
})
