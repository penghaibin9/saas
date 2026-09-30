import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/class/CounselorAssignmentView.vue', import.meta.url), 'utf8')

test('责任台账翻译三类责任且只有主辅导员提供交接入口', () => {
  assert.match(source, /PRIMARY: '主辅导员'/)
  assert.match(source, /CO: '协同辅导员'/)
  assert.match(source, /TEMP: '临时代班'/)
  assert.match(source, /row\.dutyType === 'PRIMARY'/)
})
