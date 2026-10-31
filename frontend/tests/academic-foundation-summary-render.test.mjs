import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaTermListView.vue', import.meta.url), 'utf8')
const summary = source.match(/<section v-if="!currentLoading[\s\S]*?<\/section>/)?.[0]
assert.ok(summary, '学期列表应提供当前学期摘要')
async function render(overrides = {}) {
  return renderToString(createSSRApp({
    template: summary,
    components: {
      AppButton: { setup: (_, { slots }) => () => h('button', slots.default?.()) },
      AppStatusTag: { setup: (_, { slots }) => () => h('span', slots.default?.()) }
    },
    data: () => ({ currentLoading: false, currentError: '', currentContext: {
      termId: '9007199254740999', yearCode: '2026-2027', termNo: 1,
      status: 'PUBLISHED', startDate: '2026-09-01', endDate: '2027-01-15'
    }, ...overrides }),
    methods: { hasPermission: () => false, statusLabel: () => '已发布', dateText: value => value }
  }))
}

test('当前学期摘要展示真实学期，同时隐藏无权限的后续入口', async () => {
  const html = await render()
  assert.match(html, /2026-2027 第 1 学期/)
  assert.match(html, /已发布/)
  assert.doesNotMatch(html, /查看本学期校历|核对作息时间/)
})

test('当前学期读取失败、加载中或未设置时，不展示过期学期摘要', async () => {
  for (const state of [{ currentLoading: true }, { currentError: '读取失败' }, { currentContext: null }]) {
    assert.doesNotMatch(await render(state), /2026-2027|全校当前学期/)
  }
})
