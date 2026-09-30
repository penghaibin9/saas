import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const readView = (name) => readFile(new URL(`../src/modules/academicAffairs/views/${name}`, import.meta.url), 'utf8')

test('status-change ledgers render row commands with the shared button component', async () => {
  for (const name of ['AaStatusChangeListView.vue', 'AaStatusChangeTypedListView.vue']) {
    const source = await readView(name)
    assert.match(source, /<AppButton size="small" variant="ghost" @click="goDetail\(row\)">详情 \/ 审批<\/AppButton>/)
    assert.doesNotMatch(source, /<button[^>]*>详情 \/ 审批<\/button>/)
  }
})

test('grade task entry and reminder commands use the shared button component', async () => {
  const source = await readView('AaGradeEntryView.vue')
  assert.match(source, /<AppButton size="small" variant="ghost" :disabled="writeBusy" @click="openTask\(t\)">进入<\/AppButton>/)
  assert.match(source, /<AppButton v-if="canRemind\(t\)" size="small" variant="ghost"/)
  assert.doesNotMatch(source, /<button[^>]*class="mp-link"[^>]*>进入<\/button>/)
})
