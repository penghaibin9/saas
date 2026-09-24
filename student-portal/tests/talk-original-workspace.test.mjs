import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8').replaceAll('\r', '')

test('student PC talk deep link promotes and highlights the exact summary', () => {
  assert.match(source, /tab\.value === 'talk'/)
  assert.match(source, /route\.query\.recordId/)
  assert.match(source, /const talkItems = computed/)
  assert.match(source, /String\(item\.talkId\) === focusedTalkId/)
})

test('student PC talk summary does not expose teacher internal notes', () => {
  const talkLine = source.split('\n').find((line) => line.includes(`tab === 'talk'`)) || ''
  assert.ok(talkLine)
  assert.doesNotMatch(talkLine, /item\.content|item\.result|relatedRiskId|relatedContactId/)
})
