import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const graduationResultUrl = new URL('../src/modules/academicAffairs/views/AaGraduationResultView.vue', import.meta.url)
const graduationConsoleUrl = new URL('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue', import.meta.url)
const evaluationConsoleUrl = new URL('../src/modules/academicAffairs/views/AaEvaluationConsoleView.vue', import.meta.url)
const archiveConsoleUrl = new URL('../src/modules/academicAffairs/views/AaArchiveConsoleView.vue', import.meta.url)

test('PR147 direct pagination controls do not expose an unbound page-size changer', async () => {
  const [graduationSource, evaluationSource] = await Promise.all([
    readFile(graduationResultUrl, 'utf8'),
    readFile(evaluationConsoleUrl, 'utf8')
  ])

  assert.match(graduationSource, /<AppPagination[\s\S]*?:show-size-changer="false"[\s\S]*?@change="onPaginationChange"/)
  const directEvaluationPagers = evaluationSource.match(/<AppPagination[\s\S]*?:show-size-changer="false"[\s\S]*?\/>/g) || []
  assert.equal(directEvaluationPagers.length, 4, 'all four direct Evaluation pagers must hide the unbound size changer')
})

test('PR147 graduation audit batch picker loads every server page instead of silently capping at 100', async () => {
  const source = await readFile(graduationConsoleUrl, 'utf8')
  for (const token of [
    'const pageSize = 100',
    'const all = []',
    'let page = 1',
    'let total = 0',
    'listGradBatches({ page, pageSize })',
    'all.push(...list)',
    'while (all.length < total)',
    'this.batches = all'
  ]) assert.ok(source.includes(token), `missing all-page graduation batch picker contract: ${token}`)

  assert.doesNotMatch(source, /const res = await academicAffairsApi\.listGradBatches\(\{ pageSize: 100 \}\)\s*\n\s*if \(res\.code === 0\) this\.batches = res\.data\.list/)
})

test('PR147 archive console loads every server page instead of silently capping historical batches at 100', async () => {
  const source = await readFile(archiveConsoleUrl, 'utf8')
  for (const token of [
    'const pageSize = 100',
    'const all = []',
    'let page = 1',
    'let total = 0',
    'api.listBatches({ page, pageSize })',
    'all.push(...list)',
    'while (all.length < total)',
    'this.rows = all',
    "toast.error(res.message || '归档批次加载失败')"
  ]) assert.ok(source.includes(token), `missing all-page archive batch contract: ${token}`)

  assert.doesNotMatch(source, /api\.listBatches\(\{ pageSize: 100 \}\)/)
})
