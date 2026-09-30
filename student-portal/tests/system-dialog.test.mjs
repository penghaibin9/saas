import test from 'node:test'
import assert from 'node:assert/strict'

for (const path of ['../src/services/systemDialog.js']) {
  const dialog = await import(path)
  test(`${path}: replacing a prompt cancels it without submitting a value`, async () => {
    const previous = dialog.systemPrompt('填写原因')
    const next = dialog.systemConfirm('确认操作')
    assert.equal(await previous, null)
    dialog.finishSystemDialog(false)
    assert.equal(await next, false)
  })
  test(`${path}: replacing a confirmation never accepts the previous operation`, async () => {
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
}
