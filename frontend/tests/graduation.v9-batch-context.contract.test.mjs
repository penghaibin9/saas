import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

const api = read('frontend/src/modules/graduation/api/graduation-taskbook.api.js')
const helper = read('frontend/src/modules/graduation/api/graduation-batch-context.js')
const taskbookRouter = read('backend/app/modules/graduation/routers/graduation_taskbook_sensitive_router.py')
const processRouter = read('backend/app/modules/graduation/routers/graduation_process_sensitive_router.py')

function methodBlock(name, nextName) {
  const start = api.indexOf(`${name}(`)
  assert.notEqual(start, -1, `missing ${name}`)
  const end = nextName ? api.indexOf(`${nextName}(`, start + name.length) : api.length
  assert.ok(end > start, `invalid block ${name}`)
  return api.slice(start, end)
}

test('graduation taskbook/process API resolves batch through the domain helper', () => {
  assert.match(helper, /useGraduationBatchStore/)
  assert.match(helper, /selectedBatchId/)
  assert.match(helper, /batchId:\s*String\(batchId\)/)
  assert.match(api, /import \{ withGraduationBatch \} from '@\/modules\/graduation\/api\/graduation-batch-context'/)
  assert.doesNotMatch(api, /useGraduationBatchStore/)
})

test('every taskbook/process/student-eval/midterm request carries batch params', () => {
  const methods = [
    'getTaskbook', 'issueTaskbook', 'confirmTaskbook', 'changeTaskbook', 'getTaskbookStats',
    'downloadTaskbookExport', 'exportTaskbookPdf', 'getGuidanceList', 'createGuidance', 'voidGuidance',
    'getGuidanceStats', 'getGuidancePlans', 'createGuidancePlan', 'checkinGuidancePlan', 'cancelGuidancePlan',
    'getStudentEvals', 'createStudentEval', 'submitStudentEval', 'getMidterm', 'checkMidterm',
    'submitRectification', 'reviewRectification', 'getMidtermStats',
  ]
  methods.forEach((name, index) => {
    const block = methodBlock(name, methods[index + 1])
    if (['getGuidanceList', 'getGuidancePlans', 'getStudentEvals'].includes(name)) {
      assert.match(block, /callList\(/, `${name} must use batch-safe callList`)
    } else {
      assert.match(block, /withGraduationBatch\(/, `${name} must bind batchId`)
    }
  })
})

test('backend sensitive routers keep batchId mandatory', () => {
  assert.ok((taskbookRouter.match(/batchId: int = Query\(\.\.\., ge=1\)/g) || []).length >= 7)
  assert.ok((processRouter.match(/batchId: int = Query\(\.\.\., ge=1\)/g) || []).length >= 10)
})
