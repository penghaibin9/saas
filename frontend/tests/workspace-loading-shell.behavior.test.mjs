import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { baseParse, compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'

const source = readFileSync(new URL('../src/layouts/BasePortalLayout.vue', import.meta.url), 'utf8')
const template = parse(source).descriptor.template.content
const root = baseParse(template).children.find(node => node.type === 1)
const branches = root.children.filter(node => node.type === 1 && (
  node.tag === 'TeacherWorkspaceFrame' || node.props.some(prop => prop.name === 'class' && ['bpl-body', 'bpl-workspace-pending'].includes(prop.value?.content))
))
// Exercise the actual template's branch conditions, replacing each branch's
// unrelated navigation widgets with a marker. No menu/auth data is invented.
const branchTemplate = branches.map(node => {
  const condition = node.props.find(prop => prop.name === 'if').exp.content
  const marker = node.tag === 'TeacherWorkspaceFrame' ? 'workspace-ready'
    : node.props.find(prop => prop.name === 'class').value.content
  return `<section v-if="${condition}" data-shell="${marker}"><slot /></section>`
}).join('\n')
const render = new Function('Vue', compile(branchTemplate, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
async function renderShell(useWorkspace, ctx, text = '正在加载工作台') {
  return renderToString(Vue.createSSRApp({
    render() { return Vue.h({ render, data: () => ({ useWorkspace, ctx }) }, {}, { default: () => text }) }
  }))
}

test('new workspace never renders old navigation while identity is loading, ready, or reset', async () => {
  for (const ctx of [null, { ctxKey: 'school-role' }, null]) {
    const html = await renderShell(true, ctx)
    assert.doesNotMatch(html, /data-shell="bpl-body"/)
    assert.match(html, ctx ? /workspace-ready/ : /bpl-workspace-pending/)
    assert.equal((html.match(/<section/g) || []).length, 1)
  }
})
test('loading and retry errors remain visible in the new workspace', async () => {
  assert.match(await renderShell(true, null, '加载失败，请重试'), /加载失败，请重试/)
})
test('existing non-workspace consumers keep their layout while loading', async () => {
  for (const ctx of [null, { ctxKey: 'legacy-consumer' }]) {
    const html = await renderShell(false, ctx)
    assert.match(html, /data-shell="bpl-body"/)
    assert.doesNotMatch(html, /workspace-pending|workspace-ready/)
  }
})
