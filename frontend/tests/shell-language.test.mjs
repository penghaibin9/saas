import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from 'vue/server-renderer'

const source = readFileSync(new URL('../src/layouts/BasePortalLayout.vue', import.meta.url), 'utf8').replaceAll('\r', '')

test('搜索状态用业务语言说明，入口、禁用状态和原始权限提示不变', () => {
  const rows = [
    { status: 'planned', groupKey: 'school', trail: '规划项', disabled: true, path: '/planned', badge: '待施工' },
    { status: 'partial', groupKey: 'school', trail: '部分可用项', disabled: false, path: '/partial', badge: '部分能力' },
    { status: 'unauthorized', groupKey: 'school', trail: '未开通项', disabled: true, path: '/denied', badge: '未开通' }
  ]
  const body = source.split('    fnResults() {')[1].split('\n    },')[0]
  const results = new Function('searchSearchAliases', 'searchNavPlan', 'filterAcademicTeacherSearchResults', 'hasAcademicRoleMenu', 'academicRoleSearchResults', body)
    .call({ fnQueryDebounced: '查询', workspaceStudentSearchEnabled: false, visibleGroupKeys: new Set(['school']), ctx: {}, helpApi: null }, () => [], () => rows, value => value, () => false, value => value)
  assert.deepEqual(results.map(row => row.kind), ['暂未开放', '部分可用', '未开通'])
  assert.deepEqual(results.map(row => row.to), [null, '/partial', null])
  assert.deepEqual(results.map(row => row.disabled), [true, false, true])
  assert.equal(results[2].badge, '未开通')
  assert.equal(rows[0].status, 'planned')
})

test('搜索分组已说明状态时不在每行重复状态提示', async () => {
  const snippet = source.match(/<span v-if="r.badge[^\n]*<\/span>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const kind of ['暂未开放', '部分可用', '未开通']) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ r: { kind, badge: '待施工', disabled: true } }), render }))
    assert.doesNotMatch(html, /待施工|bpl-planbadge/)
  }
  const html = await renderToString(Vue.createSSRApp({ data: () => ({ r: { kind: '功能/页面', badge: '业务提醒', disabled: false } }), render }))
  assert.match(html, /业务提醒/)
})
