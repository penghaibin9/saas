import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/components/AutoTable.vue', import.meta.url), 'utf8')

test('AutoTable 不从接口 key 自动生成表头', () => {
  assert.doesNotMatch(source, /Object\.keys\(first\).*label:\s*k/s)
  assert.match(source, /缺少 columns 展示契约/)
})

test('AutoTable 对对象单元格和未知枚举 fail closed', () => {
  assert.doesNotMatch(source, /JSON\.stringify\(v\)/)
  assert.match(source, /详细信息已收起/)
  assert.match(source, /safeVisibleEnumLabel/)
})
