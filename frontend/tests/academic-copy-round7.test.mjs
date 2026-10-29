import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page } from './academic-pc-parallel-b-harness.mjs'
import { ACADEMIC_STUDENT_STATUS_LABELS, ACADEMIC_STATUS_CHANGE_LABELS } from '../src/modules/academicAffairs/config/academicStudentLabels.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRosterListView.vue', import.meta.url), 'utf8')

test('名册不擅自打开第一名学生，姓名入口始终指向被点击的学生', async () => {
  assert.doesNotMatch(source, /goDetail\(rows\[0\]\)/)
  const template = source.match(/<template #cell-student="\{ row \}">([\s\S]*?)<\/template>/)[1]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const routes = []
  const { state } = page('AaRosterListView', {}, { $router: { push: to => routes.push(to) } })
  for (const [studentId, realName] of [['9007199254740997', '甲同学'], ['9007199254740998', '乙同学']]) {
    const row = { studentId, realName, studentNo: `S${studentId}` }
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ row }), methods: { goDetail: state.goDetail }, render }))
    assert.ok(html.includes(realName))
    assert.ok(html.includes(row.studentNo))
    const vnode = render({ row, goDetail: value => state.goDetail(value) }, [])
    vnode.children.find(child => child.type === 'button').props.onClick()
    assert.equal(routes.at(-1).name, 'aa-roster-detail')
    assert.equal(routes.at(-1).params.studentId, studentId)
  }
})

test('名册查询和页码随地址保留，刷新或返回不会丢失注册对象', async () => {
  const routes = [], requests = []
  const deps = { ACADEMIC_STUDENT_STATUS_LABELS, academicAffairsApi: { getRoster: async q => { requests.push(q); return { code: 0, data: { list: [], total: 80 } } } } }
  const { state, definition } = page('AaRosterListView', deps, { $route: { query: { keyword: 'S001', status: 'REGISTERED', page: '3' } }, $router: { replace: async r => routes.push(r) } })
  definition.created.call(state)
  assert.equal(state.pagination.page, 3)
  assert.equal(requests[0].keyword, 'S001')
  await state.search()
  assert.equal(routes[0].query.page, '1'); assert.equal(routes[0].query.status, 'REGISTERED')
  await state.onPageChange(2); assert.equal(routes[1].query.page, '2')
  definition.watch['$route.query'].handler.call(state, { keyword: 'S002', page: '4' })
  assert.equal(state.filters.keyword, 'S002'); assert.equal(state.pagination.page, 4)
  assert.equal(state.routePage('bad'), 1)
})

test('正式注册档案历史使用中文状态与本地时间，原有原因不改写', () => {
  const { state } = page('AaRosterDetailView', { ACADEMIC_STUDENT_STATUS_LABELS, ACADEMIC_STATUS_CHANGE_LABELS })
  const history = { changeId: '8', changeType: 'ENROLL_REGISTER', fromStatus: 'PENDING_REGISTER', toStatus: 'REGISTERED', status: 'EFFECTIVE', effectiveDate: '2026-10-28T14:11:30Z', reason: 'ENROLL注册' }
  state.detail = { currentStage: 'ADMITTED', studentStatus: 'REGISTERED', statusHistory: [history] }
  assert.equal(state.historyItems[0].title, '入学注册：待注册 → 在籍注册')
  assert.equal(state.historyItems[0].time, formatDateTime(history.effectiveDate))
  assert.equal(state.historyItems[0].description, '入学注册')
  assert.equal(history.reason, 'ENROLL注册')
  assert.equal(state.baseItems.find(x => x.label === '当前阶段').value, '新生阶段·已录取')
  state.detail.currentStage = 'FUTURE_STAGE'; history.changeType = 'FUTURE_CHANGE'; history.fromStatus = 'FUTURE_STATE'; history.reason = '原备注保留'
  assert.equal(state.baseItems.find(x => x.label === '当前阶段').value, '阶段待确认')
  assert.equal(state.historyItems[0].description, '原备注保留')
  assert.doesNotMatch(state.historyItems[0].title, /FUTURE/)
})
