import test from 'node:test'
import assert from 'node:assert/strict'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import * as constants from '../src/modules/academicAffairs/constants/course-program.js'
const ctx = { currentRole: {}, dataScope: {}, permissionPatterns: ['manage'] }
const mount = api => page('AaCourseConsoleView', { ...constants, matchPermission: patterns => patterns.includes('manage'), academicAffairsApi: api }, { ctx }).state
const panel = id => ({ visible: true, course: { courseId: id }, lockedType: '', loading: false, items: [], error: '' })

test('旧课程迟到材料不能覆盖新课程，错误不能伪装空材料', async () => {
  const old = deferred()
  const state = mount({ getCourseMaterials: async id => id === 'A' ? old.promise : { code: 0, data: { list: [{ title: 'B' }] } } })
  state.materialPanel = panel('A'); const reading = state.loadMaterials()
  state.materialPanel = panel('B'); await state.loadMaterials()
  old.resolve({ code: 0, data: { list: [{ title: 'A' }] } }); await reading
  assert.equal(state.materialPanel.items[0].title, 'B')
  state.materialPanel = panel('A'); old.resolve({ code: 500 })
  const failed = mount({ getCourseMaterials: async () => { throw Error('offline') } })
  failed.materialPanel = panel('A'); await failed.loadMaterials()
  assert.match(failed.materialPanel.error, /读取失败/); assert.equal(failed.materialPanel.loading, false)
})

test('上传回执只绑定原窗口，关闭或切课程后不会挂到另一课程', async () => {
  const pending = deferred(); const state = mount({ uploadCourseMaterialFile: () => pending.promise })
  state.materialPanel = panel('A')
  const upload = state.onMaterialFilePick({ target: { files: [{ name: '测试.pdf' }] } })
  state.materialPanel = panel('B'); state.resetMaterialForm()
  pending.resolve({ code: 0, data: { fileId: '11', fileName: '测试.pdf' } }); await upload
  assert.equal(state.materialForm.fileId, '')
})

test('分类保存防重入，失败保留输入；新版本成功显示确切回执', async () => {
  const pending = deferred(); let writes = 0
  const state = mount({ getCourse: async id => ({ code: 0, data: { courseId: id, courseCode: 'CS101', courseName: '原课', description: '最新说明' } }), updateCourse: async (_id, body) => { writes++; assert.equal(body.description, '最新说明'); return pending.promise } })
  state.load = async () => {}
  state.openDimForm({ courseId: '9', description: '旧说明' }, 'category'); state.dimForm.value = 'MAJOR_CORE'
  const saving = state.submitDimForm(); await state.submitDimForm()
  pending.resolve({ code: 0, data: { courseId: '10' } }); await saving
  assert.equal(writes, 1); assert.equal(state.savedCourse.courseId, '10'); assert.match(state.savedCourse.message, /新.*草稿/)
  const failed = mount({ getCourse: async () => { throw Error('offline') } })
  failed.openDimForm({ courseId: '9' }, 'category'); failed.dimForm.value = 'MAJOR_CORE'; await failed.submitDimForm()
  assert.equal(failed.dimForm.visible, true); assert.equal(failed.dimForm.value, 'MAJOR_CORE'); assert.equal(failed.saving, false); assert.match(failed.formError, /保留输入/)
})

test('材料保存中重复调用只发一次，失败保留输入', async () => {
  const pending = deferred(); let writes = 0
  const state = mount({ addCourseMaterial: async () => { writes++; return pending.promise } })
  state.materialPanel = panel('A'); state.materialForm.title = '材料标题'
  const save = state.submitMaterialForm(); await state.submitMaterialForm()
  pending.resolve({ code: 409, message: '版本已变化' }); await save
  assert.equal(writes, 1); assert.equal(state.materialForm.title, '材料标题'); assert.equal(state.materialForm.err, '版本已变化'); assert.equal(state.materialForm.submitting, false)
})

test('历史、负责人和考核筛选传到服务端，列表只取当前页', async () => {
  const calls = []; const state = mount({ getCourses: async params => { calls.push(params); return { code: 0, data: { list: [], total: 200 } } } })
  state.tab = 'archive'; state.archiveFilter = 'SUPERSEDED'; state.viewPage = 3; await state.load()
  assert.equal(calls[0].history, 'SUPERSEDED'); assert.equal(calls[0].page, 3)
  state.tab = 'owner'; state.ownerFilter = 'UNSET'; await state.load(); assert.equal(calls[1].ownerAssigned, false)
  state.tab = 'assessment'; state.dimFilter = 'EXAM'; await state.load(); assert.equal(calls[2].examMode, 'EXAM')
})
