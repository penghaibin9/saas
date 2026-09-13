import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { parse } from '@vue/compiler-sfc'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'

const layout = readFileSync(new URL('../src/layouts/BasePortalLayout.vue', import.meta.url), 'utf8')
const body = layout.split('    async loadHelp() {')[1].split('    async goPageHelp() {')[0].replace(/},\s*$/, '')
const loadHelp = new (Object.getPrototypeOf(async function() {}).constructor)('loadRuntime', 'markRaw',
  body.replace("import('@/config/helpCenterRuntime')", 'loadRuntime()'))

test('concurrent help opens share one import and failed loads can be retried', async () => {
  let calls = 0, resolve
  const state = { helpApi: null, helpLoading: false, helpError: false }
  const pending = new Promise(yes => { resolve = yes })
  const loader = () => { calls++; return pending }
  const first = loadHelp.call(state, loader, Vue.markRaw)
  const second = loadHelp.call(state, loader, Vue.markRaw)
  assert.equal(calls, 1)
  const api = { searchHelp: () => ['verified'], findHelpForRoute: () => ({ id: 'verified-page' }) }
  resolve(api)
  assert.equal(await first, api)
  assert.equal(await second, api)
  assert.equal(state.helpLoading, false)
  assert.equal(await loadHelp.call(state, loader, Vue.markRaw), api)
  assert.equal(calls, 1)

  state.helpApi = null
  await loadHelp.call(state, () => Promise.reject(new Error('offline')), Vue.markRaw)
  assert.equal(state.helpError, true)
  assert.equal(state.helpLoading, false)
  await loadHelp.call(state, () => Promise.resolve(api), Vue.markRaw)
  assert.equal(state.helpError, false)
  assert.equal(state.helpApi, api)
})

test('a closed shortcut editor creates no hidden page controls; opening still shows the full permitted list', async () => {
  const source = readFileSync(new URL('../src/components/workspace/WorkspaceShortcutEditor.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const render = new Function('Vue', compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const rows = Array.from({ length: 100 }, (_, id) => ({ id: String(id), title: `页面${id}`, trail: '本模块' }))
  const components = Object.fromEntries(['Close', 'Rank', 'ArrowUp', 'ArrowDown', 'Check'].map(key => [key, { render: () => Vue.h('svg') }]))
  const renderEditor = opened => renderToString(Vue.createSSRApp({ render, components, methods: { resetDraft() {}, save() {} }, data: () => ({
    opened, dragged: '', draft: { shortcuts: [], appearance: {} }, selectedPages: [], tab: 'add', selectedPage: null,
    availablePages: rows, query: '', dialog: null
  }) }))
  const closed = await renderEditor(false)
  assert.doesNotMatch(closed, /editor-body|checkbox|页面99/)
  const opened = await renderEditor(true)
  assert.match(opened, /页面99/)
  assert.equal((opened.match(/type="checkbox"/g) || []).length, 100)
})
