import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

function read(path) {
  return fs.readFileSync(new URL(path, import.meta.url), 'utf8').replaceAll('\r', '')
}

test('teacher talk actions come only from the server and handoffs keep exact record ids', () => {
  const source = read('../src/pages/teacher/affairs/talk/index.vue')
  assert.doesNotMatch(source, /FALLBACK_ACTIONS/)
  assert.match(source, /Array\.isArray\(this\.active && this\.active\.allowedActions\)/)
  assert.match(source, /q\.recordId \|\| q\.talkId/)
  assert.match(source, /family-contact\/index\?contactId=/)
  assert.match(source, /risk-students\/index\?recordId=/)
})

test('mental actions come only from the server and an escalation links to the exact risk', () => {
  const source = read('../src/pages/teacher/affairs/mental/index.vue')
  assert.doesNotMatch(source, /FALLBACK_ACTIONS/)
  assert.match(source, /q\.recordId \|\| q\.referralId/)
  assert.match(source, /risk-students\/index\?recordId=/)
})

test('teacher family contact workspace focuses the generated contact without a second search', () => {
  const source = read('../src/pages/teacher/family-contact/index.vue')
  assert.match(source, /q && q\.contactId/)
  assert.match(source, /findIndex\(\(item\) => String\(item\.contactId\) === this\.focusContactId\)/)
  assert.match(source, /\[rows\[index\], \.\.\.rows\.slice\(0, index\)/)
  assert.match(source, /'is-focused': String\(c\.contactId\) === focusContactId/)
})

test('student mobile talk summary accepts an exact talk deep link and preserves privacy', () => {
  const source = read('../src/pages/student/affairs/talk.vue')
  assert.match(source, /q\.recordId \|\| q\.talkId/)
  assert.match(source, /'is-focused': String\(x\.talkId\) === focusTalkId/)
  assert.match(source, /<MobileStatusTag :status="x\.status" :label="x\.statusLabel"/)
  assert.doesNotMatch(source, /x\.content|x\.result|relatedRiskId|relatedContactId/)
})
