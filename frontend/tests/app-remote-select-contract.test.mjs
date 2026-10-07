import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const componentUrl = new URL('../src/components/common/picker/AppRemoteSelect.vue', import.meta.url)

test('AppRemoteSelect 选项点击不会被外层 label 或相邻表单项截获', async () => {
  const source = await readFile(componentUrl, 'utf8')

  assert.match(source, /@mousedown\.prevent/)
  assert.match(source, /@click\.prevent\.stop="pick\(opt\)"/)
  assert.match(source, /\.app-remote-select\.is-open\s*\{\s*z-index:\s*100;/)
})

test('AppRemoteSelect 选项支持鼠标与键盘选择', async () => {
  const source = await readFile(componentUrl, 'utf8')

  assert.match(source, /role="option"/)
  assert.match(source, /@keydown\.enter\.prevent\.stop="pick\(opt\)"/)
  assert.match(source, /@keydown\.space\.prevent\.stop="pick\(opt\)"/)
  assert.match(source, /this\.\$emit\('update:modelValue', val\)/)
})

test('AppRemoteSelect 单选与多选的装饰勾选符号不改变选项无障碍名称', async () => {
  const source = await readFile(componentUrl, 'utf8')

  for (const className of ['app-remote-select__tick', 'app-remote-select__opt-check']) {
    assert.match(source, new RegExp(`<span\\b[^>]*class="${className}"[^>]*aria-hidden="true"[^>]*>✓</span>`))
  }
  assert.match(source, /:aria-selected="isChecked\(opt\.value\)"/)
  assert.match(source, /class="app-remote-select__opt-label">\{\{ opt\.label \}\}<\/span>/)
})
