import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from 'vue/server-renderer'
import { scheduleTruthPresentation } from '../src/modules/academicAffairs/components/parallel-a/scheduleTruthPresentation.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaGradeEntryView.vue', import.meta.url), 'utf8').replaceAll('\r', '')

test('生效课表显示保留异常、未发布、待核对、当前和被替代的区别', () => {
  const rows = [
    [{ truthStatus: 'INVALID' }, '', '课表版本异常', 'danger'],
    [{ truthStatus: 'NOT_PUBLISHED' }, '', '尚未发布课表', 'warning'],
    [{ truthStatus: 'VERIFIED', activeBatchId: '991', isCurrent: true }, 'PUBLISHED', '当前生效课表', 'success'],
    [{ truthStatus: 'VERIFIED', activeBatchId: '992', isCurrent: false }, 'SUPERSEDED', '已被替代', 'warning'],
    [{ truthStatus: 'VERIFIED', activeBatchId: '992', isCurrent: false }, 'PRE_PUBLISHED', '非当前生效课表', 'warning'],
    [{ truthStatus: 'VERIFIED', activeBatchId: '991' }, '', '生效版本待核对', 'warning'],
    [{ truthStatus: 'VERIFIED', activeBatchId: '991', isCurrent: false }, '', '生效版本待核对', 'warning'],
    [{ truthStatus: 'NOT_PUBLISHED', activeBatchId: '992' }, '', '生效版本待核对', 'warning'],
    [{ truthStatus: 'NEW_INTERNAL_STATUS' }, '', '生效版本待核对', 'warning']
  ]
  for (const [activeTruth, status, label, type] of rows) {
    const batch = { batchId: '991', status, activeTruth }
    const original = structuredClone(batch)
    const result = scheduleTruthPresentation(batch)
    assert.equal(result.label, label)
    assert.equal(result.type, type)
    assert.doesNotMatch(result.detail, /991|992|服务端|正式头|门禁|NEW_INTERNAL_STATUS/)
    assert.ok(result.detail.length <= 40)
    assert.deepEqual(batch, original)
  }
})

test('课表批次加载中和失败不显示零值，成功后保留原统计', async () => {
  const batch = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleBatchListView.vue', import.meta.url), 'utf8')
  const snippet = `<div>${batch.match(/<ul v-if="!onlyArchived && !loading && !error" class="aa-stat-strip"[\s\S]*?<\/ul>/)[0]}</div>`
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const [loading, error] of [[true, ''], [false, '读取失败'], [false, '']]) {
    const html = await renderToString(Vue.createSSRApp({ render, data: () => ({ loading, error, onlyArchived: false, pagination: { total: 7 } }), methods: { statusCount: () => 1 } }))
    if (loading || error) assert.doesNotMatch(html, /<b>[0-9]/)
    else { assert.match(html, /<b>7/); assert.match(html, /<b>2/) }
  }
})

test('课表批次范围和版本未知时保持待核对，学院编号不出现在正文', async () => {
  const batch = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleBatchListView.vue', import.meta.url), 'utf8')
  const scope = batch.match(/<template #cell-scope="\{ row \}">([\s\S]*?)<\/template>/)[1]
  const version = batch.match(/<template #cell-version="\{ row \}">([\s\S]*?)<\/template>/)[1]
  const render = new Function('Vue', compile(`<div>${scope}${version}</div>`, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const show = row => renderToString(Vue.createSSRApp({ render, data: () => ({ row }) }))
  assert.match(await show({}), /范围待核对[\s\S]*版本待核对/)
  const college = await show({ collegeId: '987654321012345678', activeTruth: { headVersion: 2 } })
  assert.match(college, /指定学院[\s\S]*第2版/)
  assert.doesNotMatch(college, /987654321012345678|全校范围/)
  assert.match(await show({ collegeId: null }), /全校范围/)
})

test('课表阶段栏保留五个步骤及当前索引，只说明一次当前环节', async () => {
  const stageSource = readFileSync(new URL('../src/modules/academicAffairs/components/AaScheduleStageRail.vue', import.meta.url), 'utf8')
  const component = new Function(stageSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default', 'return'))()
  const render = new Function('Vue', compile(stageSource.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const mode of ['schedule', 'scheduling']) for (const activeIndex of [0, 2, 4]) {
    const html = await renderToString(Vue.createSSRApp({ ...component, render }, { mode, activeIndex }))
    assert.equal((html.match(/<li /g) || []).length, 5)
    assert.equal((html.match(/aria-current="step"/g) || []).length, 1)
    assert.equal((html.match(/当前环节/g) || []).length, 1)
    assert.equal((html.match(/class="is-done"/g) || []).length, activeIndex)
    assert.doesNotMatch(html, /上游事实|真实状态解锁|已完成/)
  }
})

test('课表摘要保持真实状态和办理人，缺少说明时不补工程套话', async () => {
  const bar = readFileSync(new URL('../src/modules/academicAffairs/components/AaScheduleObjectBar.vue', import.meta.url), 'utf8')
  const render = new Function('Vue', compile(bar.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const html = await renderToString(Vue.createSSRApp({ render, data: () => ({ name: '课表测试', identity: '', source: '', status: '待核对', owner: '王老师', nextOwner: '教务处审核' }) }))
  assert.match(html, /待核对/)
  assert.match(html, /王老师/)
  assert.match(html, /教务处审核/)
  assert.doesNotMatch(html, /正式业务对象|排课服务|<small>|<p>/)
})

test('今日无课只显示一次，保留日期，读取失败不显示无课', async () => {
  const teacher = readFileSync(new URL('../src/modules/academicAffairs/views/AaTeacherScheduleView.vue', import.meta.url), 'utf8')
  const snippet = teacher.match(/<AppSectionCard v-if="isSelfView"[\s\S]*?<\/AppSectionCard>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const todayError of ['', '今日课表读取失败']) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ isSelfView: true, todayError, todayItems: [], todayNote: '', todayDate: '2026-10-24', todayWeek: 8 }), render,
      components: {
        AppSectionCard: { render() { return Vue.h('section', this.$slots.default()) } },
        EmptyState: { props: ['title'], render() { return Vue.h('p', this.title) } },
        ErrorState: { props: ['description'], render() { return Vue.h('p', this.description) } }
      }
    }))
    if (todayError) { assert.match(html, /读取失败/); assert.doesNotMatch(html, /今天无课/) }
    else { assert.equal((html.match(/今天无课/g) || []).length, 1); assert.match(html, /2026-10-24/) }
  }
})

test('学生课表保留学号，不用内部学生和学期编号补位', async () => {
  const student = readFileSync(new URL('../src/modules/academicAffairs/views/AaStudentScheduleView.vue', import.meta.url), 'utf8')
  const render = new Function('Vue', compile(student.match(/<AaScheduleObjectBar[\s\S]*?\/>/)[0], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const studentNo of ['', '20260001']) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ studentName: '测试同学', studentNo, studentId: '987654321012345678', termId: '876543210123456789', ctx: { currentRole: { roleName: '教务处' } } }), render,
      components: { AaScheduleObjectBar: { props: ['name', 'identity', 'source'], render() { return Vue.h('p', [this.name, this.identity, this.source].join(' ')) } } }
    }))
    assert.doesNotMatch(html, /987654321012345678|876543210123456789/)
    if (studentNo) assert.match(html, /学号 20260001/)
    assert.match(html, /本人已确认的选课/)
  }
})

test('班级课表摘要不暴露班级学期编号，保留任课范围和只读含义', async () => {
  const classSource = readFileSync(new URL('../src/modules/academicAffairs/views/AaClassScheduleView.vue', import.meta.url), 'utf8')
  const snippet = classSource.match(/<AaScheduleObjectBar[\s\S]*?\/>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const isAcademicTeacher of [true, false]) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ className: '测试班级', classId: '987654321012345678', termId: '876543210123456789', isAcademicTeacher, ctx: { currentRole: { roleName: '教师' } } }), render,
      components: { AaScheduleObjectBar: { props: ['name', 'identity', 'source', 'status'], render() { return Vue.h('p', [this.name, this.identity, this.source, this.status].join(' ')) } } }
    }))
    assert.match(html, /测试班级/)
    assert.match(html, /按所选学期查询/)
    assert.match(html, /仅供查看/)
    assert.match(html, isAcademicTeacher ? /仅可查看本人任课涉及的班级/ : /仅显示已发布的课程安排/)
    assert.doesNotMatch(html, /987654321012345678|876543210123456789|投影|范围头/)
  }
})

test('质量检查未执行时显示待检查，不能永久显示读取中', () => {
  const body = source.split('    qualityMetric() {')[1].split('\n    },')[0]
  const metric = new Function(body)
  assert.equal(metric.call({ dynamicMode: true, dynamicQuality: null, dynamicLoading: false }), '待检查')
  assert.equal(metric.call({ dynamicMode: true, dynamicQuality: null, dynamicLoading: true }), '读取中')
  assert.equal(metric.call({ dynamicMode: true, dynamicQuality: { canSubmit: false } }), '待完善')
  assert.equal(metric.call({ dynamicMode: true, dynamicQuality: { canSubmit: true } }), '可提交')
})

test('任务列表读取失败不同时显示没有任务或零项统计', async () => {
  const empty = source.match(/<EmptyState v-if="!taskLoading[^\n]+/)[0]
  const count = source.match(/<span v-if="!taskLoading[^\n]+?<\/span>/)[0]
  const render = new Function('Vue', compile(`<div>${empty}${count}</div>`, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const taskError of ['', '读取失败']) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ taskLoading: false, taskError, myTasks: [], importMode: false, taskPage: 1, taskTotal: 0 }), render,
      components: { EmptyState: { props: ['title'], render() { return Vue.h('p', this.title) } } }
    }))
    if (taskError) assert.doesNotMatch(html, /没有成绩任务|共 0 项/)
    else { assert.match(html, /当前没有成绩任务/); assert.match(html, /共 0 项/) }
  }
})

test('只读空表不指向不存在的添加控件，可编辑空表仍提示添加或加载名单', async () => {
  const snippet = source.match(/<EmptyState v-if="!rows.length" title="录入表为空"[^\n]+/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const fixedEditable of [false, true]) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ rows: [], fixedEditable }), render,
      components: { EmptyState: { props: ['description'], render() { return Vue.h('p', this.description) } } }
    }))
    assert.match(html, fixedEditable ? /添加学生或加载教学名单/ : /尚无已保存的成绩记录/)
    if (!fixedEditable) assert.doesNotMatch(html, /添加学生|从上方/)
  }
})

test('成绩项编码默认折叠但原值和编辑限制仍在', async () => {
  const snippet = source.match(/<details(?: v-if="!schemeOnly")? class="aa-code">[^\n]+<\/details>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const component = { code: 'USUAL' }
  const html = await renderToString(Vue.createSSRApp({ data: () => ({ component, writeBusy: true, schemeEditable: true }), render }))
  assert.match(html, /<details(?: v-if="!schemeOnly")? class="aa-code"><summary>实施人员使用<\/summary>/)
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/)
  assert.match(html, /disabled/)
  assert.match(html, /USUAL/)
  assert.equal(component.code, 'USUAL')
})

test('已发布成绩的统计区不重复顶部任务状态，成绩条数和成绩项保留', async () => {
  const snippet = source.match(/<section(?: v-if="!schemeOnly")? class="aa-grade-metrics"[\s\S]*?<\/section>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const html = await renderToString(Vue.createSSRApp({ data: () => ({ readOnlyResult: true, dynamicMode: false,
    rows: [{}], gradeItemMetric: '2 项', formalSchemeMode: 'fixed', hasMidterm: false,
    task: { status: 'PUBLISHED' }, rosterMetric: '1 人', qualityMetric: '可提交'
  }), methods: { statusLabel: () => '已发布' }, render }))
  assert.equal((html.match(/<article>/g) || []).length, 3)
  assert.match(html, /1 条/)
  assert.match(html, /2 项/)
  assert.doesNotMatch(html, /结果状态|已发布/)
})
