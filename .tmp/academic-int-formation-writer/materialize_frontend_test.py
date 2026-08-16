from pathlib import Path

path = Path("frontend/tests/academic-affairs-program-formation-contract.test.mjs")
if path.exists():
    raise SystemExit(f"refuse overwrite existing {path}")
path.write_text(r'''import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(
  new URL('../src/modules/academicAffairs/views/AaProgramEditorView.vue', import.meta.url),
  'utf8',
)

test('Program Editor requires an explicit direct formation mode', () => {
  assert.match(source, /v-model="addForm\.formationMode"/)
  assert.match(source, /<option value="ADMIN_FIXED">行政班固定<\/option>/)
  assert.match(source, /<option value="SELECTABLE">选课形成<\/option>/)
  assert.match(source, /addForm\.module && this\.addForm\.formationMode/)
  assert.match(source, /formationMode: this\.addForm\.formationMode/)
})

test('Program Editor does not silently default legacy or new courses to SELECTABLE', () => {
  assert.match(source, /formationMode: ''/)
  assert.doesNotMatch(source, /formationMode:\s*['"]SELECTABLE['"]\s*[,}]/)
  assert.match(source, /'未明确'/)
})
''')
