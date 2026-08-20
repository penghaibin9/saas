import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const listPage = read('src/pages/student/my-work/index.vue')
const detailPage = read('src/pages/student/my-work/detail.vue')
const legacyPage = read('src/pages/student/my-applications/index.vue')
const messagesPage = read('src/pages/student/messages/index.vue')
const manifest = JSON.parse(read('src/pages.json'))

function routes() {
  const out = new Set(manifest.pages.map((page) => page.path))
  for (const pkg of manifest.subPackages) {
    for (const page of pkg.pages) out.add(`${pkg.root}/${page.path}`)
  }
  return out
}

test('S5 我的办理列表与详情都已注册', () => {
  const registered = routes()
  assert.ok(registered.has('pages/student/my-work/index'))
  assert.ok(registered.has('pages/student/my-work/detail'))
  // 旧路由必须保留，否则历史消息深链会 404
  assert.ok(registered.has('pages/student/my-applications/index'), '旧路由不得删除，只能重定向')
})

test('S5 列表做真网络分页，不在前端切片', () => {
  // 分页/去重/epoch 失效已统一收敛到共享 networkPager（S7），页面只提供取数函数。
  assert.match(listPage, /studentApi\.getCases\(tab, cursor, pageSize\)/)
  assert.match(listPage, /nextCursor/)
  assert.match(listPage, /createNetworkPager\(/)
  assert.match(listPage, /idKey: 'caseId'/, '翻页必须按 stable id 去重')
  assert.match(listPage, /this\._pager\.reset\(\)/, '换分段必须作废旧游标与旧响应')
  // 只禁止「把全量数据拉回来再本地切片」的分页；字符串格式化用的 slice 不在此列。
  assert.doesNotMatch(listPage, /pagedSlice|listPaging/)
  assert.doesNotMatch(listPage, /items\.slice\(|rows\.slice\(/)
})

test('S5 状态分段由服务端 tabs 驱动，不在前端硬编码状态集合', () => {
  assert.match(listPage, /this\.tabs = \(data && data\.tabs\) \|\| this\.tabs/)
  assert.doesNotMatch(listPage, /APPROVED|REJECTED|PENDING_REVIEW/, '前端不得复制业务状态枚举')
})

test('S5 每条办理的动作回原业务，不落通用大厅', () => {
  assert.match(listPage, /runAction\(row\.action\)/)
  assert.match(detailPage, /runAction\(row\.action\)/)
  assert.doesNotMatch(listPage, /\/pages\/student\/campus-service\/index/)
  assert.doesNotMatch(listPage, /\/pages\/student\/affairs\/index/)
  // 没有安全入口就不渲染按钮
  assert.match(listPage, /v-if="canRun\(row\.action\)"/)
  assert.match(detailPage, /v-if="row && canRun\(row\.action\)"/)
})

test('S5 详情时间线保留每个节点的出处，不在前端合并', () => {
  assert.match(detailPage, /this\.row && this\.row\.timeline/)
  assert.match(detailPage, /node\.source \|\| `node-\$\{index\}`/)
  assert.doesNotMatch(detailPage, /nodeCode === /, '前端不得按节点码推断业务语义')
})

test('S5 列表支持 caseId 聚焦，找不到时明确告知', () => {
  assert.match(listPage, /readFocusId\(query, 'caseId'\)/)
  assert.match(listPage, /hasFocusRow\(this\.items, this\.focusId, \['caseId'\]\)/)
  assert.match(listPage, /:id="'case-' \+ row\.caseId"/)
  assert.match(listPage, /scrollToFocus\('#case-', this\.focusId\)/)
})

test('S5 旧路由重定向且带上原有 query', () => {
  assert.match(legacyPage, /uni\.redirectTo/)
  assert.match(legacyPage, /\/pages\/student\/my-work\/index/)
  assert.match(legacyPage, /key === 'recordId' \? 'caseId' : key/, '旧深链的 recordId 必须映射成新页面的聚焦参数')
  // 兼容壳不得再自己拉业务数据
  assert.doesNotMatch(legacyPage, /studentApi\./)
})

test('S5 站内入口全部指向新页面，不留两个并列入口', () => {
  for (const file of ['src/pages/student/me/index.vue', 'src/pages/student/service-apply/index.vue']) {
    assert.doesNotMatch(read(file), /my-applications/, `${file} 仍指向旧入口`)
  }
})

test('S5 消息列表的“去处理”不再按 status 猜大厅', () => {
  assert.doesNotMatch(messagesPage, /status === 'RETURNED'\) return go\(/)
  assert.doesNotMatch(messagesPage, /go\('\/pages\/student\/campus-service\/index'\)/)
  assert.match(messagesPage, /runAction\(message\.action, \{ side: 'student' \}\)/)
  assert.match(messagesPage, /canNavigate\(message && message\.action, 'student'\)/)
})
