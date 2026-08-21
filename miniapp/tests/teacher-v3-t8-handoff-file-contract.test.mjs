import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const repo = path.resolve(import.meta.dirname, '..', '..')
const handoff = JSON.parse(fs.readFileSync(path.join(repo, 'miniapp-v3-handoff.json'), 'utf8'))

test('T8 consumes a sealed Student V3 handoff with versioned shared contracts', () => {
  assert.equal(handoff.schema, 'miniapp-v3-handoff/1')
  assert.match(String(handoff.studentMergeSha || ''), /^[0-9a-f]{40}$/)
  assert.match(String(handoff.actionSchemaVersion || ''), /^\d+\.\d+\.\d+$/)
  assert.match(String(handoff.networkPagerVersion || ''), /^\d+\.\d+\.\d+$/)
  assert.match(String(handoff.attachmentPickerVersion || ''), /^\d+\.\d+\.\d+$/)
  assert.match(String(handoff.routeInventoryHash || ''), /^[0-9a-f]{64}$/)
  assert.match(String(handoff.subpackageHash || ''), /^[0-9a-f]{64}$/)
})
