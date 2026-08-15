import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/ArchivePrecheckView.vue', import.meta.url)

test('Stage D 归档预检首屏只消费后端真实语义结果与阻断计数', async () => {
  const source = await readFile(viewUrl, 'utf8')

  for (const token of [
    '归档前置门禁',
    '当前结论',
    '建议下一动作',
    'passedDomains',
    'blockedDomains',
    'blockingCount',
    'firstBlockingDomain',
    'api.precheck(this.termId || undefined)'
  ]) assert.ok(source.includes(token), `missing archive precheck Stage D token: ${token}`)

  assert.doesNotMatch(source, /healthScore|健康分|DecisionTrace|模拟阻断|mock chart/i)
})

test('Stage D 归档预检必须把阻断域放在通过域之前并按阻断项排序', async () => {
  const source = await readFile(viewUrl, 'utf8')

  assert.match(source, /blockedDomainRows\(\)/)
  assert.match(source, /\['BLOCKED', 'UNKNOWN'\]\.includes\(domain\.result\)/)
  assert.match(source, /\.sort\(\(a, b\) => Number\(b\.blockingCount \|\| 0\) - Number\(a\.blockingCount \|\| 0\)\)/)
  assert.match(source, /passedDomainRows\(\)/)
  assert.match(source, /\['PASS', 'NOT_APPLICABLE'\]\.includes\(domain\.result\)/)

  assert.ok(
    source.indexOf('归档阻断 / 待治理域') < source.indexOf('已满足门禁的业务域'),
    'blocking and unknown domains must render before non-blocking domains'
  )
})

test('Stage D 归档预检保留真实证据与责任模块跳转，不改正式归档状态机', async () => {
  const source = await readFile(viewUrl, 'utf8')

  for (const token of [
    'd.ruleCode',
    'd.summary',
    'd.evidence',
    'evidencePreview',
    'domain.route || FALLBACK_ROUTE[domain.domain]',
    "goBatch() { this.$router.push('/admin/academic-affairs/archive') }",
    '本页不写入归档事实'
  ]) assert.ok(source.includes(token), `missing archive truth token: ${token}`)
})

test('Stage D 归档预检具备阻断优先与移动端响应式收口', async () => {
  const source = await readFile(viewUrl, 'utf8')

  assert.match(source, /去处理首要阻断/)
  assert.match(source, /grid-template-columns: repeat\(4, minmax\(0,1fr\)\)/)
  assert.match(source, /@media \(max-width: 900px\)/)
  assert.match(source, /@media \(max-width: 600px\)/)
})


test('D-W1 Archive 四态必须在 UI 中可区分且 UNKNOWN 绝不绿色', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    "PASS: '通过'",
    "BLOCKED: '阻断'",
    "UNKNOWN: '待治理'",
    "NOT_APPLICABLE: '不适用'",
    "UNKNOWN: 'warning'",
    "NOT_APPLICABLE: 'info'",
    'UNKNOWN 不会被当成 PASS',
    'BLOCKED 与 UNKNOWN 均不得进入正式归档'
  ]) assert.ok(source.includes(token), `missing D-W1 archive state token: ${token}`)
})
