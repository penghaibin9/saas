import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'

const read = name => readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
function render(template, state) {
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const wrapper = { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) }
  return renderToString(Vue.createSSRApp({ data: () => state, render, components: {
    AppSectionCard: wrapper, AppButton: { setup: (_, { slots }) => () => Vue.h('button', slots.default?.()) },
    AppStatusTag: wrapper, LoadingState: { render: () => Vue.h('p', '正在加载') },
    EmptyState: { props: ['title', 'description'], setup: p => () => Vue.h('p', `${p.title} ${p.description || ''}`) }
  } }))
}

test('学院审核空队列不显示无效分页，越界页仍保留返回上一页', async () => {
  const template = read('AaGradeCollegeReviewView').match(/<aside class="aa-review-queue"[\s\S]*?<\/aside>/)[0]
  const state = { rows: [], busy: false, current: null, pagination: { total: 0, page: 1, pageSize: 20 }, onPageChange() {}, selectTask() {}, statusLabel: () => '待审核' }
  const empty = await render(template, state)
  assert.match(empty, /暂无待审核任务/)
  assert.doesNotMatch(empty, /上一页|下一页/)
  const recovery = await render(template, { ...state, pagination: { total: 0, page: 2, pageSize: 20 } })
  assert.match(recovery, /上一页/)
})

test('发布核对表保留业务对象和不完整提示，不展示内部课程教学班编号', async () => {
  const template = read('AaGradePublishView').match(/<table>[\s\S]*?<\/table>/)[0]
  const task = { courseName: '软件测试', courseId: '9007199254740997', teachingClassId: '9007199254740998', teachingClassName: '软件2601班', teacherAuthorityReady: true, teacherNames: ['授课教师'], status: 'PUBLISHED' }
  const html = await render(template, { selectedTask: task, statusLabel: () => '已发布' })
  for (const label of ['软件测试', '软件2601班', '授课教师', '不及格人数不能替代预警条数']) assert.ok(html.includes(label))
  assert.doesNotMatch(html, /9007199254740997|9007199254740998/)
  const incomplete = await render(template, { selectedTask: { ...task, courseId: null, teacherAuthorityReady: false }, statusLabel: () => '已发布' })
  assert.match(incomplete, /课程版本未关联/)
  assert.match(incomplete, /任课关系待核对/)
})

test('更正队列加载失败不同时宣称没有申请，成功空结果才显示空态', async () => {
  const content = read('AaGradeChangeView')
  const template = content.match(/<AppSectionCard title="(?:责任队列|更正申请)">[\s\S]*?<\/AppSectionCard>/)[0]
  const state = { rows: [], queueLoading: false, error: '', writeLocked: false, pagination: { page: 1 }, pageCount: 1, changePage() {} }
  assert.match(await render(template, state), /暂无/)
  assert.doesNotMatch(await render(template, { ...state, error: '读取失败' }), /暂无|没有申请/)
  const loading = await render(template, { ...state, queueLoading: true })
  assert.match(loading, /正在加载/)
  assert.doesNotMatch(loading, /暂无/)
})
