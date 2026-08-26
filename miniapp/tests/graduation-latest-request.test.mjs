import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { latestRequest } from '../src/services/latestRequest.js'

function deferred() {
  let resolvePromise
  let rejectPromise
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })
  return { promise, resolve: resolvePromise, reject: rejectPromise }
}

test('older graduation read follows the newest in-flight response', async () => {
  const first = deferred()
  const second = deferred()

  const oldCall = latestRequest('test:graduation:detail', () => first.promise)
  const newCall = latestRequest('test:graduation:detail', () => second.promise)

  first.resolve({ student: 'old' })
  second.resolve({ student: 'new' })

  assert.deepEqual(await oldCall, { student: 'new' })
  assert.deepEqual(await newCall, { student: 'new' })
})

test('stale failure follows the newer success instead of surfacing an obsolete error', async () => {
  const first = deferred()
  const second = deferred()

  const oldCall = latestRequest('test:graduation:refresh', () => first.promise)
  const newCall = latestRequest('test:graduation:refresh', () => second.promise)

  first.reject(new Error('obsolete request failed'))
  second.resolve({ version: 2 })

  assert.deepEqual(await oldCall, { version: 2 })
  assert.deepEqual(await newCall, { version: 2 })
})

test('different projection keys remain independent', async () => {
  const proposal = deferred()
  const grade = deferred()
  const proposalCall = latestRequest('test:graduation:proposal', () => proposal.promise)
  const gradeCall = latestRequest('test:graduation:grade', () => grade.promise)

  grade.resolve({ grade: 88 })
  proposal.resolve({ proposal: 'APPROVED' })

  assert.deepEqual(await proposalCall, { proposal: 'APPROVED' })
  assert.deepEqual(await gradeCall, { grade: 88 })
})

test('graduation service wrappers keep original APIs and only override race-sensitive reads', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const realSource = readFileSync(resolve(here, '../src/services/realApi.js'), 'utf8')
  const studentSource = readFileSync(resolve(here, '../src/services/studentApi.js'), 'utf8')

  assert.match(realSource, /export \* from '\.\/realApiBase'/)
  assert.match(realSource, /teacher:graduation:detail/)
  assert.match(realSource, /student:graduation:proposal/)
  assert.match(realSource, /student:graduation:archive/)
  assert.match(studentSource, /\.\.\.baseStudentApi/)
  assert.match(studentSource, /student:graduation:materials/)
})
