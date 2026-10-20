import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createStudentAcademicCommandGuard } from '../src/components/academic/studentAcademicCommandGuard.js'

class FakeStorage {
  constructor() { this.values = new Map(); this.ignoreRemove = false }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null }
  setItem(key, value) { this.values.set(key, value) }
  removeItem(key) { if (!this.ignoreRemove) this.values.delete(key) }
}

function guardFor(storage) {
  globalThis.localStorage = storage
  return createStudentAcademicCommandGuard(() => 'tenant:student:2026001:context:STUDENT:STUDENT', 'repair-check')
}

test('failed persistent deletion keeps the exact pending command blocked', () => {
  const storage = new FakeStorage()
  const guard = guardFor(storage)
  const reference = guard.preparePersistentCommand({ action: 'WRITE', objectId: '101' })
  assert.ok(reference)

  storage.ignoreRemove = true
  assert.equal(guard.completePersistentCommand(reference), false)
  assert.equal(guard.persistenceState().ok, true)
  assert.equal(guard.pendingCommands().some((item) => item.commandKey === reference.commandKey), true)
  delete globalThis.localStorage
})

test('verified deletion removes only the current command handle', () => {
  const storage = new FakeStorage()
  const guard = guardFor(storage)
  const first = guard.preparePersistentCommand({ action: 'WRITE', objectId: '101' })
  const second = guard.preparePersistentCommand({ action: 'WRITE', objectId: '102' })
  assert.ok(first); assert.ok(second)

  assert.equal(guard.completePersistentCommand(first), true)
  assert.equal(guard.pendingCommands().some((item) => item.commandKey === first.commandKey), false)
  assert.equal(guard.pendingCommands().some((item) => item.commandKey === second.commandKey), true)
  delete globalThis.localStorage
})

test('R7 application pages gate success on formal readback and verified persistence cleanup', () => {
  const pages = [
    'StudentRegistrationView.vue',
    'StudentRecognitionView.vue',
    'StudentRecheckView.vue',
    'StudentMakeupView.vue',
    'StudentMajorSplitView.vue',
    'StudentExamView.vue',
    'StudentEvaluationView.vue'
  ]
  for (const page of pages) {
    const source = readFileSync(new URL(`../src/views/academic/${page}`, import.meta.url), 'utf8')
    assert.match(source, /function persistentCommandCleared\(reference\)/)
    assert.match(source, /\['network', 'forbidden', 'conflict'\]\.includes\(kind\)/)
    assert.match(source, /kind === 'network' \|\| kind === 'conflict'/)
  }

  const makeup = readFileSync(new URL('../src/views/academic/StudentMakeupView.vue', import.meta.url), 'utf8')
  assert.match(makeup, /formal\.originGradeId \|\| formal\.gradeId/)
  assert.match(makeup, /formal\.course\?\.id \|\| formal\.courseId/)
})
