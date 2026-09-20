import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const page = readFileSync(path.join(process.cwd(), 'src/pages/student-internship/index.vue'), 'utf8')

test('student internship home adopts the server-returned current batch before rendering a multi-batch picker', () => {
  assert.match(page, /const serverBatchId = String\(this\.i\?\.batchId \|\| ''\)/)
  assert.match(page, /!this\.selectedBatchId && serverBatchId && this\.candidates\.some\(\(x\) => String\(x\.batchId\) === serverBatchId\)/)
  assert.match(page, /this\.selectedBatchId = serverBatchId\s*this\.persistBatch\(\)/)
})

test('student internship batch selector never exposes raw workflow codes as the status text', () => {
  assert.match(page, /ONBOARD: '实习中'/)
  assert.match(page, /candidateStatusLabel\(status\) \{ return INTERNSHIP_RECORD_STATUS_LABELS/)
  assert.match(page, /实习状态 \{\{ candidateStatusLabel\(candidate\.status\) \}\}/)
})
