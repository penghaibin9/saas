import test from 'node:test'
import assert from 'node:assert/strict'

import {
  invalidateAdminQueries,
  resetAdminQueryCoordinatorForTest,
  runAdminQuery
} from '../src/services/performance/queryCoordinator.js'

test.beforeEach(() => resetAdminQueryCoordinatorForTest())

test('same workbench read is single-flight', async () => {
  let calls = 0
  const loader = async () => {
    calls += 1
    await new Promise((resolve) => setTimeout(resolve, 10))
    return { pending: 3 }
  }
  const values = await Promise.all([
    runAdminQuery('teacher|todos', loader),
    runAdminQuery('teacher|todos', loader),
    runAdminQuery('teacher|todos', loader)
  ])
  assert.equal(calls, 1)
  assert.deepEqual(values.map((v) => v.pending), [3, 3, 3])
})

test('cache is isolated and write invalidation forces reload', async () => {
  let calls = 0
  const loader = async () => ({ count: ++calls, byType: { LEAVE: 1 } })
  const first = await runAdminQuery('workbench|teacher|count', loader, { ttl: 10_000 })
  first.byType.LEAVE = 99
  const second = await runAdminQuery('workbench|teacher|count', loader, { ttl: 10_000 })
  assert.equal(calls, 1)
  assert.equal(second.byType.LEAVE, 1)
  invalidateAdminQueries('workbench|teacher')
  const third = await runAdminQuery('workbench|teacher|count', loader, { ttl: 10_000 })
  assert.equal(calls, 2)
  assert.equal(third.count, 2)
})
