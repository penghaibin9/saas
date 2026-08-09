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
  assert.match(bridgeSource, /if \(!target \|\| !item\.routeName\) return item/)
  assert.match(bridgeSource, /typedRouteTarget:\s*target/)
  assert.doesNotMatch(bridgeSource, /TODO_TYPE_ROUTES|__typed_todo__/)
  assert.doesNotMatch(bridgeSource, /item\.title.*route|title.*TODO_TYPE_ROUTES/)
})

test('P1-07 workbench prefers record typedRouteTarget and keeps static todoType only as fallback', () => {
  assert.match(viewSource, /const typedTarget = String\(t\?\.typedRouteTarget \|\| ''\)\.trim\(\)/)
  assert.match(viewSource, /typedTarget \|\|[\s\S]*TODO_TYPE_ROUTES\[type\]/)
})
