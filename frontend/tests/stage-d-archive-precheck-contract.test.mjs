import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/ArchivePrecheckView.vue', import.meta.url)
const consoleUrl = new URL('../src/modules/academicAffairs/views/AaArchiveConsoleView.vue', import.meta.url)

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
    "GRADUATION: '/admin/academic-affairs/graduation/audit-console'",
    "goBatch() { this.$router.push('/admin/academic-affairs/archive') }",
    '本页不写入归档事实'
  ]) assert.ok(source.includes(token), `missing archive truth token: ${token}`)
  assert.ok(!source.includes("GRADUATION: '/admin/academic-affairs/graduation-audit'"), 'legacy graduation route must not return')
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
    'BLOCKED 与 UNKNOWN 均不得进入正式归档',
    "d.result === 'NOT_APPLICABLE' ? 'is-na' : 'is-ok'",
    'data.blockedDomains ?? fallbackBlockedDomains',
    "['BLOCKED', 'UNKNOWN'].includes(d.result)",
    '.aapc-card.is-na'
  ]) assert.ok(source.includes(token), `missing D-W1 archive state token: ${token}`)
  assert.ok(!source.includes('data.blockedDomains ||'), 'blockedDomains=0 must never fall through to legacy non-PASS counting')
})

test('D-W1 正式归档控制台必须按 result 四态展示，且不存在整体强制归档死入口', async () => {
  const source = await readFile(consoleUrl, 'utf8')

  for (const token of [
    "itemState(row)",
    "PASS: '通过'",
    "BLOCKED: '阻断'",
    "UNKNOWN: '待治理'",
    "NOT_APPLICABLE: '不适用'",
    "UNKNOWN: 'warning'",
    "NOT_APPLICABLE: 'info'",
    "itemColumns: [{ key: 'domain'",
    "{ key: 'result', title: '归档状态' }",
    '整体强制归档已停用',
    '请处理阻断 / 待治理域后重新执行完整性检查',
    "api.confirm(this.current.batchId, false)"
  ]) assert.ok(source.includes(token), `missing archive console W1 token: ${token}`)

  assert.ok(!source.includes("@click=\"doConfirm(true)\""), 'MISSING_ITEMS must not expose force-confirm action')
  assert.ok(!source.includes('>强制归档</AppButton>'), 'legacy force archive CTA must be removed')
  assert.ok(!source.includes("row.present ? 'success' : 'danger'"), 'persisted N/A/UNKNOWN must not be rendered from legacy present boolean')
})
