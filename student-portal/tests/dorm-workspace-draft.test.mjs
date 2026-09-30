import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8')
const checkSource = source.match(/function dormHasEdits\(\) \{[\s\S]*?\n\}/)[0]
const closeSource = source.match(/function closeDormForm\(\) \{[^\n]+/)[0]

function workspace() {
  const busy = { value: false }
  const form = { visible: false, buildingId: '', roomId: '', bedId: '', reason: '' }
  const notes = {}, files = {}
  const { check, close } = new Function('busy', 'dormForm', 'rectNotes', 'rectFiles',
    `${checkSource}; ${closeSource}; return {check:dormHasEdits,close:closeDormForm}`)(busy, form, notes, files)
  return { busy, form, notes, files, check, close }
}

test('opening an empty form is clean, choosing a bed protects a draft, successful close clears it', () => {
  const w = workspace()
  w.form.visible = true
  assert.equal(w.check(), false)
  Object.assign(w.form, { buildingId: '1', roomId: '1', bedId: '3', reason: '需要调整床位' })
  assert.equal(w.check(), true)
  w.busy.value = true
  w.close()
  assert.equal(w.check(), true)
  assert.equal(w.form.bedId, '3')
  w.busy.value = false
  w.close()
  assert.equal(w.check(), false)
  assert.equal(w.form.reason, '')
})

test('closing a transfer form never discards another unsent rectification or uploaded evidence', () => {
  const w = workspace()
  w.notes['7'] = '尚未提交的整改说明'
  w.files['7'] = { fileId: '123' }
  w.close()
  assert.equal(w.check(), true)
  w.notes['7'] = ''
  assert.equal(w.check(), true)
  delete w.files['7']
  assert.equal(w.check(), false)
})
