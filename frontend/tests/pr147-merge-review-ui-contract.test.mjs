import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const graduationBatchUrl = new URL('../src/modules/academicAffairs/views/AaGraduationBatchView.vue', import.meta.url)
const graduationResultUrl = new URL('../src/modules/academicAffairs/views/AaGraduationResultView.vue', import.meta.url)
const graduationConsoleUrl = new URL('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue', import.meta.url)
const evaluationConsoleUrl = new URL('../src/modules/academicAffairs/views/AaEvaluationConsoleView.vue', import.meta.url)
const studentGraduationUrl = new URL('../../student-portal/src/views/academic/StudentGraduationAuditView.vue', import.meta.url)

test('PR147 merge review: graduation batch and card result pages consume real pagination', async () => {
  const [batchSource, resultSource] = await Promise.all([
    readFile(graduationBatchUrl, 'utf8'),
    readFile(graduationResultUrl, 'utf8')
  ])

  for (const token of [
    'batchPagination: { page: 1, pageSize: 20, total: 0 }',
    ':pagination="batchPagination"',
    '@page-change="onBatchPageChange"',
    'page: this.batchPagination.page',
    'this.batchPagination.total = res.data.total'
  ]) assert.ok(batchSource.includes(token), `missing graduation batch pagination contract: ${token}`)

  for (const token of [
    'AppPagination',
    ':total="pagination.total"',
    ':page="pagination.page"',
    ':page-size="pagination.pageSize"',
    '@change="onPaginationChange"',
    'onPaginationChange({ page })',
    'this.pagination.total = res.data.total'
  ]) assert.ok(resultSource.includes(token), `missing graduation result pagination contract: ${token}`)
})

test('PR147 merge review: graduation audit course and reason views never silently cap at 100/200 rows', async () => {
  const source = await readFile(graduationConsoleUrl, 'utf8')
  for (const token of [
    'courseRequiredPagination: freshPagination()',
    'courseElectivePagination: freshPagination()',
    ':pagination="courseRequiredPagination"',
    ':pagination="courseElectivePagination"',
    'page: this.courseRequiredPagination.page',
    'page: this.courseElectivePagination.page',
    'this.courseRequiredPagination.total = req.data.total',
    'this.courseElectivePagination.total = ele.data.total',
    'reasonPagination:',
    ':pagination="g.pagination"',
    '`${g.title}（${g.total}）`',
    'page: pg.page',
    'pageSize: pg.pageSize',
    'pg.total = r.data.total'
  ]) assert.ok(source.includes(token), `missing graduation audit scale contract: ${token}`)

  assert.doesNotMatch(source, /getGradResults\(this\.batchId, \{ item: 'COURSE_REQUIRED', pageSize: 100 \}\)/)
  assert.doesNotMatch(source, /getGradResults\(this\.batchId, \{ status: g\.status, pageSize: 200 \}\)/)
})

test('PR147 merge review: graduation high-risk actions are single-flight, exception-safe, and final re-reads server truth', async () => {
  const [batchSource, resultSource, consoleSource] = await Promise.all([
    readFile(graduationBatchUrl, 'utf8'),
    readFile(graduationResultUrl, 'utf8'),
    readFile(graduationConsoleUrl, 'utf8')
  ])

  for (const source of [batchSource, resultSource, consoleSource]) {
    assert.match(source, /finally\s*\{/)
  }
  assert.match(batchSource, /this\.busy = false/)
  assert.match(resultSource, /academicAffairsApi\.getGradResult\(this\.finalDlg\.resultId\)/)
  assert.match(consoleSource, /academicAffairsApi\.getGradResult\(resultId\)/)
  assert.match(consoleSource, /if \(this\.finalDlg\.submitting \|\| !this\.detail\.row\) return/)
  assert.match(consoleSource, /if \(!this\.batchId \|\| this\.archiving\) return/)
  assert.match(consoleSource, /const note = String\(reason \|\| ''\)\.trim\(\)/)
})

test('PR147 merge review: student graduation unknown credit requirement never renders fake 100 percent', async () => {
  const source = await readFile(studentGraduationUrl, 'utf8')
  for (const token of [
    "if (raw === null || raw === undefined || raw === '') return null",
    'return Number.isFinite(value) && value > 0 ? value : null',
    "requiredCredits.value === null ? '待核验' : requiredCredits.value",
    'if (requiredCredits.value === null) return null',
    "creditPct.value === null ? '—' : creditPct.value",
    "requiredCredits.value === null ? '学分要求待核验' : '学分达成'",
    '<small v-if="creditPct !== null">%</small>'
  ]) assert.ok(source.includes(token), `missing unknown-credit fail-closed UI contract: ${token}`)

  assert.doesNotMatch(source, /if \(!requiredCredits\.value\) return obtainedCredits\.value \? 100 : 0/)
})

test('PR147 merge review: evaluation lists are keyboard reachable and server paginated', async () => {
  const source = await readFile(evaluationConsoleUrl, 'utf8')
  for (const token of [
    'role="button"',
    'tabindex="0"',
    '@keydown.enter.prevent=',
    '@keydown.space.prevent=',
    '.aaev-item:focus-visible',
    'batchPagination: freshPagination(30)',
    'archivePagination: freshPagination(30)',
    'resultPagination: freshPagination(50)',
    'appealPagination: freshPagination(50)',
    'page: this.batchPagination.page',
    'page: this.archivePagination.page',
    'page: this.resultPagination.page',
    'page: this.appealPagination.page',
    'this.resultPagination.total = res.data.total',
    'this.appealPagination.total = res.data.total',
    ':pagination="resultPagination"',
    ':pagination="appealPagination"'
  ]) assert.ok(source.includes(token), `missing evaluation production UI contract: ${token}`)

  assert.doesNotMatch(source, /api\.results\(b\.batchId, \{ pageSize: 200 \}\)/)
  assert.doesNotMatch(source, /api\.listAppeals\(\{ pageSize: 100 \}\)/)
})
