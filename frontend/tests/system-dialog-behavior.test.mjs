import test from 'node:test'
import assert from 'node:assert/strict'
import * as dialog from '../src/services/systemDialog.js'

test('frontend dialog replacement cancels a prompt without submitting a value', async () => {
  const previous = dialog.systemPrompt('填写原因')
  const next = dialog.systemConfirm('确认操作')
  assert.equal(await previous, null)
  dialog.finishSystemDialog(false)
  assert.equal(await next, false)
})

test('frontend dialog replacement never accepts the previous confirmation', async () => {
  const previous = dialog.systemConfirm('确认操作')
  const next = dialog.systemPrompt({ message: '原因', minLength: 5 })
  assert.equal(await previous, false)
  dialog.systemDialogState.value = '短'
  dialog.finishSystemDialog(true)
  assert.equal(dialog.systemDialogState.visible, true)
  assert.ok(dialog.systemDialogState.error)
  dialog.systemDialogState.value = '  已核对正式记录  '
  dialog.finishSystemDialog(true)
  assert.equal(await next, '已核对正式记录')
  assert.equal(dialog.systemDialogState.visible, false)
  dialog.finishSystemDialog(true)
})
