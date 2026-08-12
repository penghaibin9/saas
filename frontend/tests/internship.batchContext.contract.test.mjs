import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('internship module summary reuses the unified batch store and never probes dashboard without batchId', () => {
  const source = read('frontend/src/modules/internship/views/components/ModuleSummaryStrip.vue')

  assert.match(source, /useInternshipBatchStore/)
  assert.match(source, /batchStore:\s*useInternshipBatchStore\(\)/)
  assert.match(source, /batchStore\.selectedBatchId/)
  assert.match(source, /batchStore\.needsExplicitSelect/)
  assert.doesNotMatch(source, /getDashboardSummary\s*\(/)
  assert.doesNotMatch(source, /_batchCache/)
})

test('dashboard batch contract stays strict and the real dashboard supplies the selected batch explicitly', () => {
  const context = read('backend/app/modules/internship/services/internship_batch_context.py')
  const dashboard = read('frontend/src/modules/internship/views/InternshipDashboardView.vue')

  assert.match(context, /必须指定实习批次 batchId/)
  assert.match(context, /def parse_required_batch_id\(batch_id\)/)
  assert.match(dashboard, /getDashboardSummary\(\{ batchId: this\.batchStore\.selectedBatchId \}\)/)
})
