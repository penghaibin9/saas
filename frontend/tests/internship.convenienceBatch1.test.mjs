/**
 * 岗位实习 V9.3 · 便捷性批次一回归锁（U15 / U4·U6 / U8 / U10）。
 *
 * 前三段是对纯函数的真实行为测试（不是读源码字符串）：撞车判定、连续处理选下一条、
 * 工作上下文存取。第四段才是页面接线的文本断言，用来防止有人把接线删掉。
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import { isConflict, captureConflict, emptyConflict, CONFLICT_CODE }
  from '../src/modules/internship/composables/conflictGuard.js'
import { pickNextPending, anchorIndexOf }
  from '../src/modules/internship/composables/reviewQueue.js'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const view = (name) => read(`src/modules/internship/views/${name}`)

// ───────────────────────── U15 撞车判定与善后 ─────────────────────────

test('U15 只有 409 才算撞车，成功和其它失败都不能误判', () => {
  assert.equal(CONFLICT_CODE, 409001)
  assert.equal(isConflict({ code: 409001 }), true)
  assert.equal(isConflict({ code: 0 }), false)
  assert.equal(isConflict({ code: 403001 }), false)   // 无权限不是撞车
  assert.equal(isConflict({ code: 422001 }), false)   // 校验失败不是撞车
  assert.equal(isConflict({ code: 503002 }), false)   // 后端不可达不是撞车
  assert.equal(isConflict(null), false)
  // 包装层若哪天开始透传 bizCode，字符串码也要认
  assert.equal(isConflict({ code: 1, bizCode: 'DATA_CONFLICT' }), true)
  assert.equal(isConflict({ code: 1, bizCode: 'APPROVAL_VERSION_CONFLICT' }), true)
})

test('U15 撞车后拉最新真值，且只做刷新不做重放', async () => {
  const calls = []
  const state = await captureConflict({
    res: { code: 409001, message: '数据已被其他用户修改，请刷新后重试' },
    refresh: async () => { calls.push('refresh') },
    latest: () => { calls.push('latest'); return [{ label: '最新状态', value: '已办结' }] }
  })
  // 顺序必须是先刷新再取值，否则摆出来的还是旧数据
  assert.deepEqual(calls, ['refresh', 'latest'])
  assert.equal(state.active, true)
  assert.equal(state.stale, false)
  assert.match(state.message, /请确认后重新提交/)
  assert.equal(state.detail, '数据已被其他用户修改，请刷新后重试')
  assert.deepEqual(state.latest, [{ label: '最新状态', value: '已办结' }])
  // captureConflict 只认识 refresh/latest 两个回调，没有任何提交入口 —— 结构上就重放不了
  assert.equal(typeof captureConflict, 'function')
})

test('U15 最新真值拉不回来时如实标 stale，不拿旧数据冒充最新', async () => {
  let latestCalled = false
  const state = await captureConflict({
    res: { code: 409001, message: '冲突' },
    refresh: async () => { throw new Error('网络断了') },
    latest: () => { latestCalled = true; return [] }
  })
  assert.equal(state.stale, true)
  assert.equal(latestCalled, false, '刷新失败后不能再去读旧的组件状态当最新值')
  assert.deepEqual(state.latest, [])
})

test('U15 记录被别人办完后，撞车提示带回老师刚敲的原文', async () => {
  // 真机复现过的真实缺陷：撞车后拉真值，如果这条已经被别人办完，
  // 状态一变，承载表单/输入框的那块模板会被 v-if 整体换成「已处理」态，
  // 提示条如果放在同一个 v-if 里就跟着输入框一起消失，原文彻底找不回来。
  const state = await captureConflict({
    res: { code: 409001, message: '记录已发生变化，请刷新后重试' },
    refresh: async () => {},
    latest: () => [{ label: '最新状态', value: '已通过' }],
    kept: '本周联调记录完整，问题定位清晰……'
  })
  assert.equal(state.kept, '本周联调记录完整，问题定位清晰……')
})

test('U15 三个批阅/核实详情页把提示条放在状态判断之外，并把原文带回', () => {
  for (const name of ['WeeklyReportDetailView.vue', 'ProcessReportDetailView.vue', 'AttendanceExceptionDetailView.vue']) {
    const src = view(name)
    assert.match(src, /kept: this\.comment/, `${name} 撞车后应把老师刚敲的原文带进提示`)
    // 提示条必须出现在 status===PENDING_REVIEW（或 !=='COMPLETED'）判断的 template 之前，
    // 否则记录一旦被别人办完，承载它的那块表单连同提示条会一起被换掉。
    const noticeAt = src.indexOf('<ConflictNotice')
    const templateAt = src.search(/<template v-if="detail\.status/)
    assert.ok(noticeAt > -1 && templateAt > -1 && noticeAt < templateAt,
      `${name} 的 ConflictNotice 必须在状态 template 之外`)
  }
})

test('U15 清场返回的是未激活状态', () => {
  const empty = emptyConflict()
  assert.equal(empty.active, false)
  assert.deepEqual(empty.latest, [])
})

// ──────────────────── U4/U6 单页工作台的「下一条」 ────────────────────

const PENDING = (r) => r.status === 'PENDING'

test('U4/U6 优先取原位置之后的待办，取不到才回头找', () => {
  const rows = [
    { id: '1', status: 'DONE' }, { id: '2', status: 'PENDING' },
    { id: '3', status: 'DONE' }, { id: '4', status: 'PENDING' }
  ]
  // 刚处理完下标 2 那条：应该往下拿 id=4，而不是跳回顶部的 id=2
  assert.equal(pickNextPending(rows, 2, '3', PENDING).id, '4')
  // 处理的是最后一条：往下没有了，才回头拿 id=2
  assert.equal(pickNextPending(rows, 3, '4', PENDING).id, '2')
})

test('U4/U6 排除自己，避免原地打转', () => {
  const rows = [{ id: '7', status: 'PENDING' }]
  assert.equal(pickNextPending(rows, 0, '7', PENDING), null)
})

test('U4/U6 没有待办时返回 null，由页面提示队列已清空', () => {
  const rows = [{ id: '1', status: 'DONE' }, { id: '2', status: 'APPROVED' }]
  assert.equal(pickNextPending(rows, 0, '1', PENDING), null)
  assert.equal(pickNextPending([], 0, '1', PENDING), null)
  assert.equal(pickNextPending(null, 0, '1', PENDING), null)
})

test('U4/U6 锚点找不到时从头找，不会漏掉待办', () => {
  const rows = [{ id: '1', status: 'PENDING' }, { id: '2', status: 'PENDING' }]
  assert.equal(anchorIndexOf(rows, '2'), 1)
  assert.equal(anchorIndexOf(rows, 'not-exist'), 0)
  assert.equal(pickNextPending(rows, anchorIndexOf(rows, 'not-exist'), 'not-exist', PENDING).id, '1')
})

// ───────────────────────── U8 工作上下文 ─────────────────────────

// 必须 await 后再拆桩：直接 return fn(store) 的话 finally 会在异步体跑完之前
// 就把假 sessionStorage 撤掉，测试会拿到空存储而误判。
async function withFakeSessionStorage(fn) {
  const store = new Map()
  const prev = globalThis.sessionStorage
  globalThis.sessionStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k)
  }
  try { return await fn(store) } finally { globalThis.sessionStorage = prev }
}

test('U8 筛选条件按路由分桶存取，刷新后能原样找回', async () => {
  await withFakeSessionStorage(async () => {
    const wc = await import('../src/modules/internship/composables/workContext.js?case=roundtrip')
    const vm = {
      $route: { path: '/admin/internship/attendance', query: {} },
      keyword: '张三', statusFilter: 'PENDING', page: 3
    }
    wc.captureWorkContext(vm, ['keyword', 'statusFilter', 'page'])
    const fresh = {
      $route: { path: '/admin/internship/attendance', query: {} },
      keyword: '', statusFilter: '', page: 1
    }
    assert.equal(wc.restoreWorkContext(fresh, ['keyword', 'statusFilter', 'page']), true)
    assert.equal(fresh.keyword, '张三')
    assert.equal(fresh.statusFilter, 'PENDING')
    assert.equal(fresh.page, 3)
    // 另一个页面不能被串台
    const other = { $route: { path: '/admin/internship/scores', query: {} }, keyword: '', page: 1 }
    assert.equal(wc.restoreWorkContext(other, ['keyword', 'page']), false)
    assert.equal(other.keyword, '')
  })
})

test('U8 支持 filters.status 这类点号路径', async () => {
  await withFakeSessionStorage(async () => {
    const wc = await import('../src/modules/internship/composables/workContext.js?case=path')
    const vm = {
      $route: { path: '/p', query: {} },
      filters: { keyword: 'abc', status: 'PENDING_HANDLE' },
      pagination: { page: 5, pageSize: 10 }
    }
    const fields = ['filters.keyword', 'filters.status', 'pagination.page']
    wc.captureWorkContext(vm, fields)
    const fresh = {
      $route: { path: '/p', query: {} },
      filters: { keyword: '', status: '' },
      pagination: { page: 1, pageSize: 10 }
    }
    assert.equal(wc.restoreWorkContext(fresh, fields), true)
    assert.equal(fresh.filters.status, 'PENDING_HANDLE')
    assert.equal(fresh.pagination.page, 5)
  })
})

test('U8 深链优先：URL 带了显式参数就不恢复上次筛选', async () => {
  await withFakeSessionStorage(async () => {
    const wc = await import('../src/modules/internship/composables/workContext.js?case=deeplink')
    wc.saveWorkContext('/admin/internship/scores', { statusFilter: 'PUBLISHED' })
    const vm = { $route: { path: '/admin/internship/scores', query: { stage: 'recheck' } }, statusFilter: '' }
    assert.equal(wc.restoreWorkContext(vm, ['statusFilter'], { skipWhenQuery: ['stage'] }), false)
    assert.equal(vm.statusFilter, '', '带 ?stage= 的待办链接不能被上次筛选改写')
  })
})

test('U8 只存筛选类标量，不把整行业务数据塞进去', async () => {
  await withFakeSessionStorage(async (store) => {
    const wc = await import('../src/modules/internship/composables/workContext.js?case=scalar')
    const vm = {
      $route: { path: '/p', query: {} },
      keyword: 'k',
      rows: [{ id: 1, studentName: '张三', idCard: '身份证号' }]
    }
    wc.captureWorkContext(vm, ['keyword', 'rows'])
    const raw = store.get('internshipWorkContext') || ''
    assert.match(raw, /"keyword":"k"/)
    assert.doesNotMatch(raw, /studentName|idCard/, '业务数据不得落进 sessionStorage')
  })
})

test('U8 上下文过期后作废，不让上午的筛选下午还生效', async () => {
  await withFakeSessionStorage(async (store) => {
    const wc = await import('../src/modules/internship/composables/workContext.js?case=ttl')
    wc.saveWorkContext('/p', { keyword: 'k' })
    const all = JSON.parse(store.get('internshipWorkContext'))
    all['/p'].savedAt = Date.now() - 9 * 60 * 60 * 1000
    store.set('internshipWorkContext', JSON.stringify(all))
    assert.equal(wc.readWorkContext('/p'), null)
  })
})

// ─────────────────── 页面接线（防止被删掉的文本断言） ───────────────────

test('U15 五个写操作页面都接了撞车提示，且不在冲突分支里关弹窗', () => {
  for (const name of [
    'RiskDisposalView.vue', 'InternshipComplianceView.vue', 'WeeklyReportDetailView.vue',
    'ProcessReportDetailView.vue', 'AttendanceExceptionDetailView.vue',
    'InternshipApplicationReviewView.vue', 'AttendanceView.vue'
  ]) {
    const src = view(name)
    assert.match(src, /ConflictNotice/, `${name} 应渲染撞车提示`)
    assert.match(src, /isConflict/, `${name} 应判定撞车`)
    assert.match(src, /captureConflict/, `${name} 应拉最新真值`)
  }
})

test('U10 缺项筛选交给服务端，本地那次过滤必须删干净', () => {
  const src = view('ScoreView.vue')
  assert.match(src, /params\.incompleteOnly = true/, '必须把 incompleteOnly 传给后端')
  assert.doesNotMatch(src, /displayRows/, '本地按页过滤会让第 3 页看不到第 5 页的缺项')
  assert.doesNotMatch(src, /接口暂不支持全量缺项过滤/, '文案不能再说接口不支持')
})

test('U10 后端确实认这个参数（前端不能对着不存在的契约接线）', () => {
  const router = read('../backend/app/modules/internship/routers/internship.py')
  assert.match(router, /incompleteOnly: bool = Query\(False/)
  assert.match(router, /incomplete_only=incompleteOnly/)
})

test('U4/U6 连续处理已覆盖到本批新接的两页', () => {
  assert.match(view('InternshipApplicationReviewView.vue'), /advanceAfterReview/)
  assert.match(view('AttendanceView.vue'), /advanceAfterHandle/)
  // 补卡/异常是表格页，下一条只给入口不自动弹窗，避免误点到下一个学生
  assert.match(view('AttendanceView.vue'), /openNextUp/)
})

test('U8 五个工作台都保持了刷新前的筛选', () => {
  for (const name of [
    'AttendanceExceptionListView.vue', 'InternshipApplicationReviewView.vue',
    'AttendanceView.vue', 'ScoreView.vue', 'WeeklyReportListView.vue'
  ]) {
    const src = view(name)
    assert.match(src, /restoreWorkContext/, `${name} 应恢复上次筛选`)
    assert.match(src, /captureWorkContext/, `${name} 应保存当前筛选`)
  }
})

// ───────── 收尾批：把「后端有、前端没入口」的两条链路补上 ─────────

test('U15 巡访计划状态迁移有了前端入口，且接了撞车提示', () => {
  const src = view('GuidanceVisitView.vue')
  assert.match(src, /transitionVisitPlan/, '页面必须真的调用状态迁移接口')
  assert.match(src, /PLAN_ACTIONS/, '按钮要按状态机白名单出，不能全都摆出来')
  // 与后端 internship_visit_plan_service._TRANSITIONS 逐条对齐
  for (const a of ['PUBLISH', 'START', 'COMPLETE', 'CANCEL']) {
    assert.match(src, new RegExp(`'${a}'`), `缺少动作 ${a}`)
  }
  assert.match(src, /ConflictNotice/)
  assert.match(src, /isConflict/)
})

test('U15 巡访计划的动作白名单不能与后端状态机脱节', () => {
  const svc = read('../backend/app/modules/internship/services/internship_visit_plan_service.py')
  // 后端白名单：PUBLISH(DRAFT) / START(PUBLISHED) / COMPLETE(IN_PROGRESS) / CANCEL(三者)
  assert.match(svc, /"PUBLISH":\s*\(\("DRAFT",\),\s*"PUBLISHED"\)/)
  assert.match(svc, /"START":\s*\(\("PUBLISHED",\),\s*"IN_PROGRESS"\)/)
  assert.match(svc, /"COMPLETE":\s*\(\("IN_PROGRESS",\),\s*"COMPLETED"\)/)
  const src = view('GuidanceVisitView.vue')
  assert.match(src, /DRAFT:\s*\[/)
  assert.match(src, /PUBLISHED:\s*\[/)
  assert.match(src, /IN_PROGRESS:\s*\[/)
})

test('U15 企业考察审核有了前端入口，且接了撞车提示', () => {
  const src = view('InternshipEnterpriseDetailView.vue')
  assert.match(src, /listInspections/, '要能列出考察记录')
  assert.match(src, /createInspection/, '要能登记考察')
  assert.match(src, /submitInspection/, '要能提交审核')
  assert.match(src, /reviewInspection/, '要能通过/驳回')
  assert.match(src, /ConflictNotice/)
  assert.match(src, /isConflict/)
})

test('U10 导出口径与屏幕筛选一致（前后端都要认这个参数）', () => {
  const view_ = view('ScoreView.vue')
  assert.match(view_, /params\.incompleteOnly = true[\s\S]{0,400}exportScores|exportScores[\s\S]{0,400}incompleteOnly/,
    '导出必须带上当前的缺项筛选')
  const router = read('../backend/app/modules/internship/routers/internship.py')
  assert.match(router, /scores\/export[\s\S]{0,600}incompleteOnly/, '导出端点要接这个参数')
  const svc = read('../backend/app/modules/internship/services/internship_score_service.py')
  assert.match(svc, /def export_scores\([\s\S]{0,200}incomplete_only/)
  assert.match(svc, /incomplete_only=incomplete_only/, '必须真的透传给 list_scores')
})

test('U15 巡访页把 require-reason 改成可配置后，旧动作不能退化成选填', () => {
  // 模板原本硬编码 :require-reason="true"，为了让"发布/开始/完成"不逼老师编字才改成
  // cd.requireReason。改完之后**每一处 cd 赋值**都必须显式带上这个字段，否则撤销指导记录、
  // 巡访整改跟进会从"原因必填"悄悄变成"可不填"——而撤销原因是要写审计的。
  const src = view('GuidanceVisitView.vue')
  assert.match(src, /:require-reason="cd\.requireReason"/)
  // 只在每个 cd 赋值块内部找，不能全文件数 requireReason（PLAN_ACTIONS 里也有）
  const blocks = src.split('this.cd = {').slice(1)
  assert.ok(blocks.length >= 3, `cd 赋值点应有 3 处，实际 ${blocks.length}`)
  blocks.forEach((block, i) => {
    // 不能用 indexOf('}') 找块尾：内容里有 `${a.label}` 这种模板插值，会被提前截断。
    // 三处 cd 赋值都以 submitting 结尾，切到它即可覆盖整个对象。
    const body = block.slice(0, block.indexOf('submitting:'))
    assert.match(body, /requireReason:/,
      `第 ${i + 1} 处 cd 赋值没写 requireReason，会退化成原因选填：${body.slice(0, 120)}`)
  })
})

test('U15 企业考察按钮走实习模块的权限码体系，不能混用 permissionActions', () => {
  // 这页历史上用 permissionActions（动作名，如 reviewEnterprise）+ can()/reason()；
  // 企业考察是后端 require_permission 的点号权限码，两套不是一个体系。
  // 早期写成 !!perms['internship.enterprise.inspection.manage'] 有两个错：
  // 键取不到（永远 undefined→按钮永久置灰），而且 !!对象 会绕过 .allowed 判定。
  const src = view('InternshipEnterpriseDetailView.vue')
  assert.match(src, /canCode\(this\.ctx, 'internship\.enterprise\.inspection\.manage'\)/)
  assert.doesNotMatch(src, /!!perms\['internship\./,
    '点号权限码不能去 permissionActions 里取')
})
