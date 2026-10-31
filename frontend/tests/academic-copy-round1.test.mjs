import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import postcss from 'postcss'
import { page } from './academic-pc-parallel-b-harness.mjs'

const read = file => readFileSync(new URL(`../src/modules/academicAffairs/${file}`, import.meta.url), 'utf8')
function cell(source, name) {
  const fragment = source.match(new RegExp(`<template #cell-${name}="\\{ row \\}">([\\s\\S]*?)<\\/template>`))?.[1]
  assert.ok(fragment, `缺少 ${name} 单元格`)
  return new Function('Vue', compile(fragment, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
}
const renderCell = (source, name, row) => renderToString(Vue.createSSRApp({ data: () => ({ row }), render: cell(source, name) }))

for (const [view, idKey, nameKey, businessName, slot] of [
  ['AaProgramListView', 'programId', 'programName', '软件技术2026级培养方案', 'programs'],
  ['AaCourseListView', 'courseId', 'courseName', '软件测试技术', 'courses']
]) {
  test(`${view} 保留业务名称和对象跳转，列表不显示内部编号`, async () => {
    const source = read(`views/${view}.vue`)
    const row = { [idKey]: '9007199254740997', [nameKey]: businessName, courseCode: 'RJ2026', version: 3, courseCount: 18 }
    const html = await renderCell(source, 'name', row)
    assert.match(html, new RegExp(businessName))
    assert.doesNotMatch(html, /9007199254740997|正式方案|正式课程/)
    const detail = await renderCell(source, slot === 'courses' ? 'code' : 'version', row)
    assert.match(detail, /第 3 版/)
    if (slot === 'courses') assert.match(detail, /RJ2026/)
    else assert.match(html, /18 门课程/)
    const destinations = []
    const { state } = page(view, { matchPermission: () => false }, { $route: { query: {}, fullPath: `/admin/academic-affairs/${slot}` }, ctx: { permissionPatterns: [] }, $router: { push: to => destinations.push(to) } })
    state.row = row
    const vnode = cell(source, 'actions')(state, [])
    vnode.props.onClick()
    assert.equal(destinations[0].path, `/admin/academic-affairs/${slot}/${row[idKey]}`)
    assert.equal(destinations[0].query.returnTo, `/admin/academic-affairs/${slot}`)
  })
}

test('教学任务窄屏筛选使用本页的纵向拉伸规则，不被教务共享横向规则覆盖', () => {
  const shared = postcss.parse(read('styles/business-workspace.css'))
  shared.walkRules(rule => {
    if (rule.selector.includes('.task-batch-filters')) {
      rule.walkDecls('align-items', decl => assert.ok(!['end', 'flex-end'].includes(decl.value), '共享规则会把纵向筛选框挤到右侧'))
    }
  })
  const local = postcss.parse(read('views/AaTaskBatchListView.vue').match(/<style scoped>([\s\S]*?)<\/style>/)[1])
  let responsiveStretch = false
  local.walkAtRules('media', media => {
    if (media.params.includes('760px')) media.walkRules('.task-batch-filters', rule => {
      const declarations = Object.fromEntries(rule.nodes.filter(node => node.type === 'decl').map(node => [node.prop, node.value]))
      responsiveStretch = declarations['flex-direction'] === 'column' && declarations['align-items'] === 'stretch'
    })
  })
  assert.equal(responsiveStretch, true)
})
