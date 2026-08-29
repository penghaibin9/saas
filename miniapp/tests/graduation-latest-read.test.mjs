import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

import { latestRead } from '../src/services/latestRead.js'

function deferred() {
  let resolvePromise
  let rejectPromise
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })
  return { promise, resolve: resolvePromise, reject: rejectPromise }
}

test('stale mobile read follows the newest result', async () => {
  const oldRead = deferred()
  const newRead = deferred()
  const oldCall = latestRead('test:graduation:detail', () => oldRead.promise)
  const newCall = latestRead('test:graduation:detail', () => newRead.promise)

  oldRead.resolve({ studentId: 1 })
  newRead.resolve({ studentId: 2 })

  assert.deepEqual(await oldCall, { studentId: 2 })
  assert.deepEqual(await newCall, { studentId: 2 })
})

test('obsolete error does not replace a newer successful projection', async () => {
  const oldRead = deferred()
  const newRead = deferred()
  const oldCall = latestRead('test:graduation:process', () => oldRead.promise)
  const newCall = latestRead('test:graduation:process', () => newRead.promise)

  oldRead.reject(new Error('obsolete network failure'))
  newRead.resolve({ version: 9 })

  assert.deepEqual(await oldCall, { version: 9 })
  assert.deepEqual(await newCall, { version: 9 })
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
  assert.match(teacherSource, /latestRead\('teacher:graduation:detail'/)
  assert.match(teacherSource, /real\.gdTeacherGradeDetail\(id\)/)
})
