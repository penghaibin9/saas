import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../src/modules/graduation/views/GraduationTemplateView.vue', import.meta.url), 'utf8')

test('V6 template workbench exposes all three canonical template types in one page', () => {
  for (const type of ['MATERIAL', 'TASKBOOK', 'PROPOSAL']) {
    assert.ok(source.includes(`value: '${type}'`), `missing template type ${type}`)
  }
  for (const label of ['材料模板', '任务书模板', '开题模板']) {
    assert.ok(source.includes(label), `missing template label ${label}`)
  }
  assert.match(source, /switchType\(type\)/)
})

test('V6 template list restores type status and page without changing routes', () => {
  assert.match(source, /buildRouteQuery\(overrides = \{\}\)/)
  assert.match(source, /type: this\.activeType/)
  assert.match(source, /status: this\.filters\.status \|\| undefined/)
  assert.match(source, /page: this\.pagination\.page > 1/)
  assert.match(source, /applyRouteState\(query = \{\}\)/)
  assert.match(source, /this\.\$router\.replace\(\{ query: this\.buildRouteQuery/)
})

test('V6 archived templates are read-only and cannot re-enter write commands', () => {
  assert.match(source, /row\.status === 'ARCHIVED'/)
  assert.match(source, /归档只读/)
  assert.match(source, /row\.status !== 'ARCHIVED'/)
  assert.match(source, /row\.status === 'ARCHIVED'\) return/)
  assert.match(source, /归档后永久只读，但历史引用继续保留/)
})

test('V6 template reads are latest-wins and writes freeze their command context', () => {
  assert.match(source, /loadToken: 0/)
  assert.match(source, /const token = \+\+this\.loadToken/)
  assert.match(source, /token !== this\.loadToken/)
  assert.match(source, /commandSnapshot: null/)
  assert.match(source, /rowId: row\.id/)
  assert.match(source, /routeQuery: this\.buildRouteQuery\(\)/)
  assert.match(source, /beforeRouteLeave\(to, from, next\)/)
  assert.match(source, /if \(this\.submitting\)/)
  assert.match(source, /next\(false\)/)
  assert.match(source, /finally \{/)
  assert.match(source, /this\.commandSnapshot = null/)
})
