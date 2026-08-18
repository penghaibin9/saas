import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const graduationResultUrl = new URL('../src/modules/academicAffairs/views/AaGraduationResultView.vue', import.meta.url)
const evaluationConsoleUrl = new URL('../src/modules/academicAffairs/views/AaEvaluationConsoleView.vue', import.meta.url)

test('PR147 direct pagination controls do not expose an unbound page-size changer', async () => {
  const [graduationSource, evaluationSource] = await Promise.all([
    readFile(graduationResultUrl, 'utf8'),
    readFile(evaluationConsoleUrl, 'utf8')
  ])

  assert.match(graduationSource, /<AppPagination[\s\S]*?:show-size-changer="false"[\s\S]*?@change="onPaginationChange"/)
  const directEvaluationPagers = evaluationSource.match(/<AppPagination[\s\S]*?:show-size-changer="false"[\s\S]*?\/>/g) || []
  assert.equal(directEvaluationPagers.length, 4, 'all four direct Evaluation pagers must hide the unbound size changer')
})
