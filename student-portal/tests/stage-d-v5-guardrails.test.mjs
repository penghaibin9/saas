import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (relative) => readFile(new URL(`../${relative}`, import.meta.url), 'utf8')

test('V5 家长入口必须使用独立公开 GuardianView，不得重定向学生登录页', async () => {
  const source = await read('src/router/index.js')
  assert.match(source, /path:\s*['"]\/guardian['"][\s\S]*?name:\s*['"]guardian['"][\s\S]*?meta:\s*\{\s*public:\s*true\s*\}[\s\S]*?GuardianView\.vue/)
  assert.doesNotMatch(source, /path:\s*['"]\/guardian['"][^\n]*redirect:\s*['"]\/login['"]/)
})

test('V5 主题专项点击当前真实主题控件而不是已退役 selector', async () => {
  const source = await read('review/v5-full-review.mjs')
  assert.match(source, /getByRole\(['"]group['"],\s*\{\s*name:\s*['"]切换门户主题['"]\s*\}\)/)
  assert.match(source, /sp-theme-switch__item/)
  assert.doesNotMatch(source, /\.sp-theme__item/)
})

test('毕业资格证据不得把 student_status 技术枚举直接展示给学生', async () => {
  const source = await read('src/views/academic/StudentGraduationAuditView.vue')
  assert.match(source, /localizeVisibleEnumText/)
  assert.match(source, /function itemEvidenceText\(item\)/)
  assert.match(source, /\^student_status=/)
  assert.match(source, /当前学籍状态：/)
  assert.doesNotMatch(source, /<p>\{\{\s*item\.evidence\s*\|\|/)
})

test('校园蓝首页小字使用经 Chromium 对比度复核的 Stage D 覆盖层', async () => {
  const main = await read('src/main.js')
  const css = await read('src/styles/stage-d-v5-fixes.css')
  assert.match(main, /stage-d-v5-fixes\.css/)
  assert.match(css, /home-chip small/)
  assert.match(css, /home-stage :where\(span, small\)/)
  assert.match(css, /#58738b/i)
})
