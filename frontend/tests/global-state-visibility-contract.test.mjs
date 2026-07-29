import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const globalStateUrl = new URL('../src/components/common/AppGlobalState.vue', import.meta.url)
const tokensUrl = new URL('../src/styles/tokens.css', import.meta.url)
const receiptUrl = new URL('../src/modules/studentAffairs/views/FamilyReceiptView.vue', import.meta.url)

test('业务页二次加载保留已有内容并展示轻量刷新状态', async () => {
  const source = await readFile(globalStateUrl, 'utf8')

  assert.match(source, /state === 'loading' && hasReadyContent/)
  assert.match(source, /class="ags-refreshing"/)
  assert.match(source, /if \(value === 'ready'\) this\.hasReadyContent = true/)
})

test('历史主题变量都有可见的语义色兼容映射', async () => {
  const source = await readFile(tokensUrl, 'utf8')

  for (const token of [
    '--color-primary',
    '--color-primary-light',
    '--color-danger',
    '--color-warning',
    '--color-bg-subtle',
    '--color-border',
    '--color-text-secondary',
    '--color-text-tertiary'
  ]) {
    assert.match(source, new RegExp(`${token}:`))
  }
})

test('家校回执筛选保留列表并呈现真实状态数量', async () => {
  const source = await readFile(receiptUrl, 'utf8')

  assert.match(source, /load\(\{ preserveContent: true \}\)/)
  assert.match(source, /filterCount\(f\.key\)/)
  assert.match(source, /res\.data\.statusCounts/)
  assert.doesNotMatch(source, /const full = await studentAffairsApi\.getFamilyContactsAll/)
})
