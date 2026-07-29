import test from 'node:test'
import assert from 'node:assert/strict'

import {
  invalidateCoordinatedQueries,
  resetQueryCoordinatorForTest,
  runCoordinatedQuery
} from '../src/services/queryCoordinator.js'

test.beforeEach(() => resetQueryCoordinatorForTest())

test('concurrent identical reads share one loader', async () => {
  let calls = 0
  const loader = async () => {
    calls += 1
    await new Promise((resolve) => setTimeout(resolve, 10))
    return { value: 1 }
  }
  const [a, b, c] = await Promise.all([
    runCoordinatedQuery('student|home', loader),
    runCoordinatedQuery('student|home', loader),
    runCoordinatedQuery('student|home', loader)
  ])
  assert.equal(calls, 1)
  assert.deepEqual(a, { value: 1 })
  assert.deepEqual(b, { value: 1 })
  assert.deepEqual(c, { value: 1 })
})

test('short cache returns isolated values and invalidation reloads', async () => {
  let calls = 0
  const loader = async () => ({ count: ++calls, nested: { ok: true } })
  const first = await runCoordinatedQuery('student|messages', loader, { ttl: 10_000 })
  first.nested.ok = false
  const second = await runCoordinatedQuery('student|messages', loader, { ttl: 10_000 })
  assert.equal(calls, 1)
  assert.equal(second.nested.ok, true)
  invalidateCoordinatedQueries('messages')
  const third = await runCoordinatedQuery('student|messages', loader, { ttl: 10_000 })
  assert.equal(calls, 2)
  assert.equal(third.count, 2)
})

test('different identities and force requests never share stale data', async () => {
  let calls = 0
  const loader = async () => ({ count: ++calls })
  await runCoordinatedQuery('student-a|home', loader, { ttl: 10_000 })
  await runCoordinatedQuery('student-b|home', loader, { ttl: 10_000 })
  await runCoordinatedQuery('student-a|home', loader, { ttl: 10_000, force: true })
  assert.equal(calls, 3)
})
