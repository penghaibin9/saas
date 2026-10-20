import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

import { latestRead } from '../src/services/latestRead.js'
import { advanceSessionGeneration, __resetSessionGenerationForTests } from '../src/services/sessionGeneration.mjs'

function deferred() {
  let resolvePromise
  let rejectPromise
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })
  return { promise, resolve: resolvePromise, reject: rejectPromise }
}

test('obsolete mobile read never receives the newer private result', async () => {
  __resetSessionGenerationForTests()
  const oldRead = deferred()
  const newRead = deferred()
  const oldCall = latestRead('test:graduation:detail', () => oldRead.promise)
  const newCall = latestRead('test:graduation:detail', () => newRead.promise)

  oldRead.resolve({ studentId: 1 })
  newRead.resolve({ studentId: 2 })

  await assert.rejects(oldCall, error => error.code === 'STALE_READ' && error.staleRead === true)
  assert.deepEqual(await newCall, { studentId: 2 })
})

test('obsolete error is also stale and cannot replace a newer successful projection', async () => {
  __resetSessionGenerationForTests()
  const oldRead = deferred()
  const newRead = deferred()
  const oldCall = latestRead('test:graduation:process', () => oldRead.promise)
  const newCall = latestRead('test:graduation:process', () => newRead.promise)

  oldRead.reject(new Error('obsolete network failure'))
  newRead.resolve({ version: 9 })

  await assert.rejects(oldCall, error => error.code === 'STALE_READ' && error.staleRead === true)
  assert.deepEqual(await newCall, { version: 9 })
})

test('an old request cannot revive after a completed newer request and a third read', async () => {
  __resetSessionGenerationForTests()
  const firstRead = deferred()
  const secondRead = deferred()
  const thirdRead = deferred()
  const firstCall = latestRead('test:graduation:aba', () => firstRead.promise)
  const secondCall = latestRead('test:graduation:aba', () => secondRead.promise)

  secondRead.resolve({ version: 2 })
  assert.deepEqual(await secondCall, { version: 2 })

  const thirdCall = latestRead('test:graduation:aba', () => thirdRead.promise)
  firstRead.resolve({ version: 1 })
  await assert.rejects(firstCall, error => error.code === 'STALE_READ' && error.staleRead === true)

  thirdRead.resolve({ version: 3 })
  assert.deepEqual(await thirdCall, { version: 3 })
})

test('a login-generation change rejects an old projection even if its loader resolves', async () => {
  __resetSessionGenerationForTests()
  const read = deferred()
  const oldCall = latestRead('student:graduation:overview', () => read.promise)
  advanceSessionGeneration()
  read.resolve({ studentId: 'A' })
  await assert.rejects(oldCall, error => error.code === 'SESSION_CHANGED' && error.staleSession === true)
})

test('graduation freshness guards live in student/teacher adapters without replacing canonical realApi', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const realSource = readFileSync(resolve(here, '../src/services/realApi.js'), 'utf8')
  const studentSource = readFileSync(resolve(here, '../src/services/studentApi.js'), 'utf8')
  const teacherSource = readFileSync(resolve(here, '../src/services/teacherApi.js'), 'utf8')

  assert.match(realSource, /export async function studentHomeReal\(\)/)
  assert.match(realSource, /acadSelectionPreflight/)
  assert.match(studentSource, /real\.studentHomeReal\(\)/)
  assert.match(studentSource, /latestRead\('student:graduation:proposal'/)
  assert.match(studentSource, /latestRead\('student:graduation:materials'/)
  assert.match(teacherSource, /latestRead\(`teacher:graduation:proposal:\$\{id\}`/)
  assert.match(teacherSource, /latestRead\(`teacher:graduation:final:\$\{id\}`/)
  assert.match(teacherSource, /real\.gdTeacherGradeDetail\(id\)/)
})
