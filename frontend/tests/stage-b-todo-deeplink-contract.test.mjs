import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const apiSource = fs.readFileSync(new URL('../src/modules/workbench/api/workbench.api.js', import.meta.url), 'utf8')
const bridgeSource = fs.readFileSync(new URL('../src/modules/workbench/config/todoTypedRouteBridge.js', import.meta.url), 'utf8')

test('P1-07 workbench read path consumes typed todo DTO before rendering', () => {
  assert.match(apiSource, /adaptTypedTodoPage/)
  assert.match(apiSource, /todos:\s*adaptTypedTodoPage\(snapshot\.todos\)/)
  assert.match(apiSource, /todo-list[\s\S]*\.then\(adaptTypedTodoPage\)/)
})

test('P1-07 typed route target comes from server routePath and query, not title guessing', () => {
  assert.match(bridgeSource, /item\?\.routePath/)
  assert.match(bridgeSource, /item\?\.query/)
  assert.match(bridgeSource, /if \(!target \|\| !item\.routeName\) return item/)
  assert.match(bridgeSource, /TODO_TYPE_ROUTES\[key\] = target/)
  assert.doesNotMatch(bridgeSource, /item\.title.*route|title.*TODO_TYPE_ROUTES/)
})
