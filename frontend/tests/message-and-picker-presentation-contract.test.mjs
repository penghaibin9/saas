import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('正式消息页面不暴露沙箱账号与环境编码', () => {
  const source = read('../src/modules/messageCenter/views/MessageComposeView.vue')
    + read('../src/modules/messageCenter/views/MessageOutboxView.vue')
  assert.doesNotMatch(source, /admin2|demo-school|sandbox-school|密码见|演示账号/)
})

test('通知发布使用业务字段生成参数且不显示 actionKey fallback', () => {
  const source = read('../src/modules/messageCenter/views/MessageComposeView.vue')
  assert.doesNotMatch(source, /a\.label \|\| a\.actionKey/)
  assert.doesNotMatch(source, /深链参数（JSON/)
  assert.match(source, /form\.actionParams\[param\]/)
  assert.match(source, /仅可选择当前账号负责范围内的接收对象/)
})

test('学工 picker 缺标签时禁用且不拼接数据库 ID', () => {
  const source = read('../src/modules/studentAffairs/pickerAdapters.js')
  assert.match(source, /label: missingLabel \? '名称待同步'/)
  assert.match(source, /disabled: missingLabel/)
  assert.doesNotMatch(source, /认定批次 #|资助项目 #|归档批次 #|楼栋 #|房间 #/)
  assert.doesNotMatch(source, /bedNo \|\| firstDefined/)
})
