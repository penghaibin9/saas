import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { DEFAULT_MAX_ITEMS, DEFAULT_PAGE_SIZE, createNetworkPager } from '../src/utils/networkPager.js'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const searchPage = read('src/pages/common/search/index.vue')
const providers = read('src/services/searchProviders.js')
const notify = read('src/pages/common/notify-settings/index.vue')
const myWork = read('src/pages/student/my-work/index.vue')

// ── §11.3 networkPager ──

test('S7 首屏与续页都走网络，loadMore 到底后是空操作', async () => {
  let calls = 0
  const pager = createNetworkPager(async (cursor) => {
    calls += 1
    return cursor ? { items: [{ id: 'b' }], nextCursor: '' } : { items: [{ id: 'a' }], nextCursor: 'c1' }
  })
  await pager.refresh()
  assert.deepEqual(pager.state.items.map((i) => i.id), ['a'])
  assert.equal(pager.state.hasMore, true)
  await pager.loadMore()
  assert.deepEqual(pager.state.items.map((i) => i.id), ['a', 'b'])
  assert.equal(pager.state.hasMore, false)
  await pager.loadMore()
  assert.equal(calls, 2, '到底之后不得再打请求')
})

test('S7 加载中重复 loadMore 不会重复打同一页', async () => {
  let calls = 0
  let release
  const gate = new Promise((resolve) => { release = resolve })
  const pager = createNetworkPager(async () => {
    calls += 1
    await gate
    return { items: [{ id: String(calls) }], nextCursor: 'next' }
  })
  const first = pager.refresh()
  pager.loadMore()
  pager.loadMore()
  release()
  await first
  assert.equal(calls, 1)
})

test('S7 按 stable id 去重；没有 id 的条目直接丢弃', async () => {
  const pager = createNetworkPager(async (cursor) =>
    cursor
      ? { items: [{ id: 'a' }, { id: 'c' }, {}], nextCursor: '' }
      : { items: [{ id: 'a' }, { id: 'b' }, { id: 'a' }], nextCursor: 'c1' })
  await pager.refresh()
  await pager.loadMore()
  assert.deepEqual(pager.state.items.map((i) => i.id), ['a', 'b', 'c'])
})

test('S7 refresh/reset 之后旧响应必须被丢弃', async () => {
  let resolveSlow
  const slow = new Promise((resolve) => { resolveSlow = resolve })
  let first = true
  const pager = createNetworkPager(async () => {
    if (first) {
      first = false
      await slow
      return { items: [{ id: 'stale' }], nextCursor: '' }
    }
    return { items: [{ id: 'fresh' }], nextCursor: '' }
  })
  const stale = pager.refresh()
  await pager.refresh()
  resolveSlow()
  await stale
  assert.deepEqual(pager.state.items.map((i) => i.id), ['fresh'], '过期响应不得覆盖新结果')

  pager.reset()
  assert.deepEqual(pager.state.items, [])
  assert.equal(pager.state.cursor, '')
  assert.equal(pager.state.hasMore, false)
})

test('S7 单页内存有上限，长列表不会无界增长', async () => {
  assert.equal(DEFAULT_PAGE_SIZE, 20)
  assert.equal(DEFAULT_MAX_ITEMS, 100)
  let page = 0
  const pager = createNetworkPager(async () => {
    page += 1
    return {
      items: Array.from({ length: 20 }, (_, i) => ({ id: `p${page}-${i}` })),
      nextCursor: page < 10 ? `c${page}` : ''
    }
  }, { pageSize: 20, maxItems: 60 })
  await pager.refresh()
  for (let i = 0; i < 9; i += 1) await pager.loadMore()
  assert.equal(pager.state.items.length, 60, '超过上限时丢弃最旧的，不无界增长')
  assert.equal(pager.state.items[pager.state.items.length - 1].id, 'p10-19')
})

test('S7 my-work 复用共享 pager，不再自己手写分页', () => {
  assert.match(myWork, /import \{ createNetworkPager \} from '@\/utils\/networkPager'/)
  assert.match(myWork, /createNetworkPager\(/)
  assert.match(myWork, /idKey: 'caseId'/)
  // 换分段必须作废旧 pager，否则上一段的游标会串过来
  assert.match(myWork, /if \(this\._pager\) this\._pager\.reset\(\)/)
})

// ── §9.4 side-aware search shell ──

test('S7 搜索壳不绑定任何一端 API', () => {
  assert.match(searchPage, /resolveSearchProvider/)
  assert.doesNotMatch(searchPage, /studentApi|teacherApi/, '共享壳不得直接引用某一端 API')
  assert.doesNotMatch(searchPage, /\/mobile\/student\//, '共享壳不得硬编码某一端接口路径')
})

test('S7 provider 按 side 分流，且教师端不冒充服务端检索', () => {
  assert.match(providers, /side === 'teacher' \? teacherProvider : studentProvider/)
  assert.match(providers, /serverSide: true/)
  assert.match(providers, /serverSide: false/)
  assert.match(providers, /仅搜索本机已加载的消息/, '教师端必须说明它只搜本地已加载数据')
  // 主包页面引用它，因此不能拖入某一端 API 与 mock 图（S1.5）
  assert.doesNotMatch(providers, /from '@\/services\/(studentApi|teacherApi)'/)
})

test('S7 学生搜索有防抖与 epoch 失效，短关键词不发请求', () => {
  assert.match(searchPage, /DEBOUNCE_MS = 300/)
  assert.match(searchPage, /this\._epoch !== epoch/)
  assert.match(searchPage, /if \(value\.length < this\.minLength\) return/)
})

// ── §9.3 站内 vs 微信订阅 ──

test('S7 通知设置把站内分类与微信订阅分成两个区块', () => {
  assert.match(notify, /站内消息分类/)
  assert.match(notify, /微信重要提醒/)
  assert.match(notify, /wechatSubscribeStatus/)
})

test('S7 微信侧状态只认服务端，未配置/未授权都如实显示', () => {
  assert.match(notify, /v-if="!wechat\.configured"/)
  assert.match(notify, /学校尚未开通微信提醒/)
  assert.match(notify, /wechat\.effective \? '已授权' : '未授权'/)
  // 点过按钮不等于开启：授权结果必须回服务端复核
  assert.match(notify, /complete: \(\) => \{[\s\S]*?this\.load\(\)/)
})

test('S7 订阅授权只由用户点击触发，且只请求已配置的模板', () => {
  assert.match(notify, /requestSubscribe\(\)/)
  assert.match(notify, /@click="requestSubscribe"/)
  assert.match(notify, /scenes \|\| \[\]\)\.filter\(\(scene\) => scene\.ready\)/)
  assert.match(notify, /if \(!this\.wechat\.configured \|\| !ready\.length\)/)
  assert.doesNotMatch(notify, /onLoad[\s\S]{0,200}requestSubscribeMessage/, '不得在页面加载时自动弹授权')
})
