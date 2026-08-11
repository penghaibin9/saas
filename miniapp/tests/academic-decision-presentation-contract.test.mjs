import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('移动端规则卡默认只展示业务依据，技术元数据需高级角色二次展开', async () => {
  const source = await readFile(new URL('../src/components/MobileAcademicDecisionCard.vue', import.meta.url), 'utf8')
  assert.match(source, /规则依据：\{\{ ruleBasis \}\}/)
  assert.match(source, /technicalOpen/)
  assert.match(source, /audience === 'admin' \|\| this\.audience === 'platformAdmin'/)
  assert.doesNotMatch(source, /showAuditMeta\(\).*teacher/)
})
