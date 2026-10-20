import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8').replaceAll('\r', '')

test('student PC can request a teacher contact and receives a real submission receipt', () => {
  assert.match(source, /v-model="psyWantsContact"/)
  assert.match(source, /wantsContact: psyWantsContact\.value/)
  assert.match(source, /psyResult\.value = result\.data/)
  assert.match(source, /已登记人工关注，请留意老师联系/)
})

test('student PC history renders the actual safe survey contract', () => {
  assert.match(source, /item\.submissionId/)
  assert.match(source, /item\.wantsContact/)
  assert.match(source, /item\.triggeredAttention/)
  assert.doesNotMatch(source, /PSY_HISTORY_COLS/)
  assert.doesNotMatch(source, /item\.answers|reasonSummary|counselorNote/)
})
