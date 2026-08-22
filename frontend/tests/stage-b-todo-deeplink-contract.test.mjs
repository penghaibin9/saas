import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const apiSource = fs.readFileSync(new URL('../src/modules/workbench/api/workbench.api.js', import.meta.url), 'utf8')
const bridgeSource = fs.readFileSync(new URL('../src/modules/workbench/config/todoTypedRouteBridge.js', import.meta.url), 'utf8')
const viewSource = fs.readFileSync(new URL('../src/modules/workbench/views/WorkbenchView.vue', import.meta.url), 'utf8')

test('P1-07 workbench read path consumes typed todo DTO before rendering', () => {
  assert.match(apiSource, /adaptTypedTodoPage/)
  assert.match(apiSource, /todos:\s*adaptTypedTodoPage\(snapshot\.todos\)/)
  assert.match(apiSource, /todo-list[\s\S]*\.then\(adaptTypedTodoPage\)/)
})

test('P1-07 typed route target comes from server routePath/query, not title guessing', () => {
  assert.match(bridgeSource, /item\?\.routePath/)
  assert.match(bridgeSource, /item\?\.query/)
  assert.match(bridgeSource, /if \(!target \|\| !item\.routeName\) return \{ \.\.\.item, focusMode: 'NONE' \}/)
  assert.match(bridgeSource, /typedRouteTarget:\s*target/)
  assert.doesNotMatch(bridgeSource, /TODO_TYPE_ROUTES|__typed_todo__/)
  assert.doesNotMatch(bridgeSource, /item\.title.*route|title.*TODO_TYPE_ROUTES/)
  // V3 施工手册 TP-W07：bridge 必须显式给出 focusMode（DETAIL/NONE），consumer 才能
  // 区分"精确对象"和"只是安全入口"，不能把 NONE 假装成已经定位到对象。
  assert.match(bridgeSource, /focusMode:\s*item\.routeExact \? 'DETAIL' : 'NONE'/)
})

test('P1-07 workbench fail-closed when server gives no typedRouteTarget, not local guessing', () => {
  // V3 施工手册 TP-W06：openTodo() 不再拿 TODO_TYPE_ROUTES 或拼 todoType/status
  // 兜底猜路由——那条路径不保证真的存在对应能力，点了可能落进空壳或全量列表，
  // 误导成"已处理"。没有服务端 typedRouteTarget 就必须禁用 + 提示，而不是导航。
  assert.match(viewSource, /const typedTarget = String\(t\?\.typedRouteTarget \|\| ''\)\.trim\(\)/)
  assert.match(viewSource, /if \(!typedTarget\) \{/)
  assert.doesNotMatch(viewSource, /typedTarget \|\|[\s\S]*TODO_TYPE_ROUTES\[type\]/)
  assert.doesNotMatch(viewSource, /TODO_TYPE_ROUTES\[type\]/)
})
