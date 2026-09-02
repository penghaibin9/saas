import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../src/modules/graduation/views/DefenseScheduleView.vue', import.meta.url), 'utf8')

test('V6 defense schedule restores batch group filter and return context', () => {
  for (const key of ['batchId', 'groupId', 'filter', 'returnTo']) {
    assert.ok(source.includes(key), `missing defense work-context key ${key}`)
  }
  assert.match(source, /buildRouteQuery\(overrides = \{\}\)/)
  assert.match(source, /applyRouteState\(query = \{\}\)/)
  assert.match(source, /this\.\$router\.replace\(\{ query: this\.buildRouteQuery/)
  assert.match(source, /currentReturnTo\(\)/)
})

test('V6 defense reads are latest-wins and bound to the selected batch', () => {
  assert.match(source, /loadToken: 0/)
  assert.match(source, /const token = \+\+this\.loadToken/)
  assert.match(source, /token !== this\.loadToken \|\| batchId !== String\(this\.batchStore\.selectedBatchId/)
  assert.match(source, /getDefenseSchedules\(\{ page: 1, pageSize: 50, batchId \}\)/)
})

test('V6 publish freezes the exact group and rereads server state before showing success', () => {
  assert.match(source, /action: 'PUBLISH'/)
  assert.match(source, /batchId: String\(this\.batchStore\.selectedBatchId\)/)
  assert.match(source, /groupId: String\(row\.id\)/)
  assert.match(source, /routeQuery: this\.buildRouteQuery/)
  assert.match(source, /publishDefenseSchedule\(snapshot\.groupId\)/)
  assert.match(source, /await this\.load\(\)/)
  assert.match(source, /服务器最新状态/)
  assert.match(source, /正式权限、数据范围与状态机仍由服务端裁决/)
})

test('V6 notification freezes one group and prevents duplicate submits until server receipt', () => {
  assert.match(source, /action: 'NOTIFY'/)
  assert.match(source, /notifyDefense\(snapshot\.groupId\)/)
  assert.match(source, /this\.actionBusy = `notify:\$\{snapshot\.groupId\}`/)
  assert.match(source, /服务器回执：已送达/)
  assert.match(source, /当前按钮已防重复提交/)
  assert.match(source, /if \(this\.contextLocked \|\| !row\?\.published\) return/)
})

test('V6 defense write commands reject route and batch context changes', () => {
  assert.match(source, /beforeRouteLeave\(to, from, next\)/)
  assert.match(source, /if \(this\.contextLocked\)/)
  assert.match(source, /next\(false\)/)
  assert.match(source, /if \(String\(batchId \|\| ''\) !== String\(snapshot\.batchId \|\| ''\)\) this\.batchStore\.selectBatch\(snapshot\.batchId\)/)
  assert.match(source, /restoreCommandContext\(\)/)
})

test('V6 preflight visibly checks all obvious schedule gaps but does not replace backend validation', () => {
  for (const gap of ['missingJudges', 'conflicts', 'missingLocation', 'missingTime', 'missingSecretary', 'studentsOverLimit']) {
    assert.ok(source.includes(gap), `missing defense preflight fact ${gap}`)
  }
  assert.match(source, /students > 30/)
  assert.match(source, /页面预检覆盖六类明显缺口，但不能替代服务端权限、数据范围、回避规则和发布状态机/)
})
