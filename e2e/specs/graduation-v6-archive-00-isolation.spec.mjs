import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

test.describe.serial('V6 · archive filing isolation preflight', () => {
  test('closes only RUNNING Playwright batches created by this exact GitHub run', async ({}, testInfo) => {
    const runBase = String(process.env.GITHUB_RUN_ID || '').replace(/\D/g, '').slice(-12)
    expect(runBase, 'archive isolation requires the exact GitHub Actions run id').toMatch(/^\d+$/)

    const batchPrefix = `PW-E2E-${runBase}`
    const adminApi = await loginApi(config.sandboxAdmin)
    const batches = items(await adminApi.get('/graduation/batches', {
      keyword: batchPrefix,
      page: 1,
      pageSize: 200
    }))
    const currentRunBatches = batches.filter(batch => String(batch.batchNo || '').startsWith(batchPrefix))
    const running = currentRunBatches.filter(batch => String(batch.status || '').toUpperCase() === 'RUNNING')
    const closed = []

    for (const batch of running) {
      const batchNo = String(batch.batchNo || '')
      expect(batchNo.startsWith(batchPrefix), 'preflight must never close a batch outside this exact CI run').toBe(true)

      const receipt = await adminApi.post(`/graduation/batches/${batch.id}/close`, {})
      expect(String(receipt?.status || '').toUpperCase()).toBe('CLOSED')
      const readback = await adminApi.get(`/graduation/batches/${batch.id}`)
      expect(String(readback?.status || '').toUpperCase()).toBe('CLOSED')
      closed.push({ id: String(batch.id), batchNo })
    }

    const after = items(await adminApi.get('/graduation/batches', {
      keyword: batchPrefix,
      page: 1,
      pageSize: 200
    }))
    const remainingRunning = after.filter(batch =>
      String(batch.batchNo || '').startsWith(batchPrefix)
      && String(batch.status || '').toUpperCase() === 'RUNNING'
    )
    expect(remainingRunning, 'no earlier batch from this exact run may remain RUNNING before the archive chain').toEqual([])

    await testInfo.attach('graduation-archive-isolation-receipt', {
      body: Buffer.from(JSON.stringify({
        head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
        runId: process.env.GITHUB_RUN_ID || '',
        batchPrefix,
        closed,
        remainingRunning: []
      }, null, 2)),
      contentType: 'application/json'
    })
  })
})
