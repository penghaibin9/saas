import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const editor = fs.readFileSync(
  path.join(root, 'src/modules/academicAffairs/views/AaProgramEditorView.vue'),
  'utf8'
)
const api = fs.readFileSync(
  path.join(root, 'src/modules/academicAffairs/api/academic-affairs.api.js'),
  'utf8'
)

test('A-W2 program binding UI exposes optional class override with exact scope query', () => {
  assert.match(editor, /AppClassPicker/)
  assert.match(editor, /majorId: program\.majorId/)
  assert.match(editor, /grade: bindForm\.gradeYear/)
  assert.match(editor, /classStatus: 'NORMAL'/)
  assert.match(editor, /班级特例（可选）/)
  assert.match(editor, /留空=专业年级通用；选择班级=仅该班覆盖/)
})

test('A-W2 program binding passes classId through the mature shared API contract', () => {
  assert.match(
    editor,
    /bindProgramGrade\(this\.programId, this\.bindForm\.gradeYear, classId\)/
  )
  assert.match(api, /bindProgramGrade\(programId, gradeYear, classId\)/)
  assert.match(api, /body: \{ gradeYear, classId \}/)
})

test('A-C2 program course picker makes exact course version visible before locking courseId', () => {
  assert.match(editor, /:remote-search="searchProgramCourses"/)
  assert.match(editor, /status: 'ENABLED'/)
  assert.match(editor, /`v\$\{course\.version\}`/)
  assert.match(editor, /value: String\(course\.courseId\)/)
  assert.match(editor, /course\.courseCode/)
})

async function courseForm(api, { navigationFails = false, editId = '' } = {}) {
  const source = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaCourseFormView.vue'), 'utf8')
  const dependencies = { academicAffairsApi: api, toast: { success() {}, error() {} }, matchPermission: () => true }
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies`)
    .replace('export default', 'return')
  let dirty = true, confirmations = 0
  const browser = { __SAAS_DIRTY_FORM_GUARD__: { handlesRoute: () => false, markSaved: () => { dirty = false } } }
  const definition = new Function('dependencies', 'window', script)(dependencies, browser)
  const state = { ctx: { permissionPatterns: [] }, $route: { params: { id: editId } }, ...definition.data() }
  for (const [key, method] of Object.entries(definition.methods)) state[key] = method.bind(state)
  for (const [key, getter] of Object.entries(definition.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  state.form = { ...state.form, courseCode: 'VA261004', courseName: '联调实践课', description: '已填写的联调课程说明' }
  // Render the actual textarea component and page binding: fieldset inheritance
  // does not set a descendant's native disabled property.
  const textareaSource = fs.readFileSync(path.join(root, 'src/components/common/form/AppTextarea.vue'), 'utf8')
  const textarea = new Function(textareaSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default', 'return'))()
  textarea.render = compile(textareaSource.match(/<template>([\s\S]*?)<\/template>/)[1])
  const textareaBinding = source.match(/<AppTextarea\b[^>]*\/>/)[0]
  let rendered = ''
  state.$nextTick = async () => {
    rendered = await renderToString(createSSRApp({ components: { AppTextarea: textarea }, data: () => ({ form: state.form, saveCompleted: state.saveCompleted }), render: compile(textareaBinding) }))
  }
  await state.$nextTick()
  const workspace = fs.readFileSync(path.join(root, 'src/components/workspace/TeacherWorkspaceFrame.vue'), 'utf8')
  const guard = workspace.slice(workspace.indexOf('async function confirmUnsubmitted('), workspace.indexOf('\nonBeforeRouteLeave(confirmUnsubmitted)'))
  const readOnly = () => /<textarea\b[^>]*\sreadonly(?:\s|>|=)/.test(rendered)
  const document = { querySelectorAll: () => [{ readOnly: readOnly(), disabled: /<textarea\b[^>]*\sdisabled(?:\s|>|=)/.test(rendered), value: state.form.description, getClientRects: () => [1] }] }
  const confirm = new Function('window', 'document', 'systemConfirm', `${guard}; return confirmUnsubmitted`)(browser, document, async () => { confirmations++; return true })
  const destinations = []
  state.$router = { push: async destination => {
    destinations.push(destination)
    await confirm({ path: destination }, { path: '/admin/academic-affairs/courses/new' })
    if (navigationFails === 'resolved') return { type: 4 }
    if (navigationFails) throw new Error('导航暂不可用')
  } }
  const switchCourse = async id => { const old = state.courseId; state.$route.params.id = id; const watcher = definition.watch?.courseId; if (watcher) await (typeof watcher === 'function' ? watcher : watcher.handler).call(state, id, old); await state.$nextTick() }
  return { state, destinations, switchCourse, unmount: () => definition.beforeUnmount?.call(state), dirty: () => dirty, confirmations: () => confirmations, readOnly, leave: () => confirm({ path: '/admin/academic-affairs/courses' }, { path: '/admin/academic-affairs/courses/new' }) }
}

test('课程保存成功清除未保存状态并直接打开返回档案，不再要求丢弃已提交内容', async () => {
  let creates = 0
  const f = await courseForm({ createCourse: async () => { creates++; return { code: 0, data: { courseId: '9007199254740993' } } } })
  await f.state.submit()
  assert.equal(creates, 1)
  assert.equal(f.dirty(), false)
  assert.equal(f.confirmations(), 0)
  assert.equal(f.readOnly(), true)
  assert.deepEqual(f.destinations, ['/admin/academic-affairs/courses/9007199254740993'])
  assert.equal(f.state.form.description, '已填写的联调课程说明')
})

test('课程保存被拒绝或请求失败保留可编辑输入与未保存防护', async () => {
  for (const createCourse of [async () => ({ code: 1, message: '保存失败' }), async () => { throw new Error('网络失败') }]) {
    const f = await courseForm({ createCourse })
    await f.state.submit()
    assert.equal(f.dirty(), true)
    assert.equal(f.state.submitting, false)
    assert.equal(f.state.saveCompleted, false)
    assert.equal(f.state.form.description, '已填写的联调课程说明')
    assert.deepEqual(f.destinations, [])
    assert.equal(f.readOnly(), false)
    await f.leave()
    assert.equal(f.confirmations(), 1)
  }
})

test('保存成功但导航失败后只重试打开同一档案，不重复创建课程', async () => {
  for (const navigationFails of [true, 'resolved']) {
    let creates = 0
    const f = await courseForm({ createCourse: async () => { creates++; return { code: 0, data: { courseId: '5330' } } } }, { navigationFails })
    await f.state.submit(); await f.state.submit()
    assert.equal(creates, 1)
    assert.deepEqual(f.destinations, ['/admin/academic-affairs/courses/5330', '/admin/academic-affairs/courses/5330'])
    assert.equal(f.confirmations(), 0)
    assert.equal(f.state.saveCompleted, true)
    assert.equal(f.state.submitting, false)
    assert.match(f.state.formError, /课程已保存/)
  }
})

test('保存中重复点击只有一次写入，启用课程编辑打开返回的新版本', async () => {
  let finish, updates = 0
  const response = new Promise(resolve => { finish = resolve })
  const f = await courseForm({ updateCourse: async id => { assert.equal(id, '4670'); updates++; return response } }, { editId: '4670' })
  const saving = f.state.submit()
  await f.state.submit()
  assert.equal(updates, 1)
  finish({ code: 0, data: { courseId: '5331' } }); await saving
  assert.deepEqual(f.destinations, ['/admin/academic-affairs/courses/5331'])
  assert.equal(f.confirmations(), 0)
})

test('服务端已确认保存但缺档案编号时停止重复写入', async () => {
  let creates = 0
  const f = await courseForm({ createCourse: async () => { creates++; return { code: 0, data: {} } } })
  await f.state.submit(); await f.state.submit()
  assert.equal(creates, 1)
  assert.equal(f.state.saveCompleted, true)
  assert.match(f.state.formError, /档案编号/)
  assert.deepEqual(f.destinations, [])
})


test('已保存表单直接切新建清除回执和旧草稿，恢复正常创建', async () => {
  let creates = 0
  const f = await courseForm({ updateCourse: async () => ({ code: 0, data: { courseId: '5330' } }), createCourse: async () => { creates++; return { code: 0, data: { courseId: '5332' } } } }, { editId: '5330', navigationFails: true })
  await f.state.submit()
  await f.switchCourse('')
  assert.equal(f.state.saveCompleted, false)
  assert.equal(f.state.savedCourseId, '')
  assert.equal(f.state.form.courseName, '')
  assert.equal(f.readOnly(), false)
  f.state.form.courseCode = 'NEW101'; f.state.form.courseName = '新课程'
  await f.state.submit()
  assert.equal(creates, 1)
  assert.equal(f.destinations.at(-1), '/admin/academic-affairs/courses/5332')
})

test('直接切另一编辑对象读新课程，读取失败清空旧输入且禁止更新', async () => {
  let updates = 0
  const f = await courseForm({ getCourse: async id => id === '5331' ? { code: 0, data: { courseName: '另一课程', courseCode: 'NEW101', credit: 2, status: 'DRAFT' } } : { code: 1, message: '读取失败' }, updateCourse: async () => { updates++; return { code: 0, data: { courseId: '5330' } } } }, { editId: '5330', navigationFails: true })
  await f.state.submit()
  await f.switchCourse('5331')
  assert.equal(f.state.form.courseName, '另一课程')
  assert.equal(f.state.saveCompleted, false)
  await f.switchCourse('5332')
  assert.equal(f.state.form.courseName, '')
  assert.match(f.state.formError, /读取失败/)
  f.state.form.courseCode = 'TRY101'; f.state.form.courseName = '不得冒充已读取课程'
  await f.state.submit()
  assert.equal(updates, 1)
})

test('旧课程迟到读取不覆盖新对象，旧保存回执不锁定或导航新表单', async () => {
  let finishRead, finishSave
  const oldRead = new Promise(resolve => { finishRead = resolve })
  const oldSave = new Promise(resolve => { finishSave = resolve })
  const f = await courseForm({ getCourse: async () => oldRead, updateCourse: async () => oldSave }, { editId: '5330' })
  const reading = f.state.loadCourse()
  await f.switchCourse('')
  f.state.form.courseCode = 'NEW101'; f.state.form.courseName = '新草稿'
  finishRead({ code: 0, data: { courseName: '旧课程', courseCode: 'OLD101', credit: 3 } }); await reading
  assert.equal(f.state.form.courseName, '新草稿')
  await f.switchCourse('5330') // Start another delayed read only after its promise resolved.
  const saving = f.state.submit()
  await f.switchCourse('')
  f.state.form.courseName = '切换后的草稿'
  finishSave({ code: 0, data: { courseId: '5331' } }); await saving
  assert.equal(f.state.form.courseName, '切换后的草稿')
  assert.equal(f.state.saveCompleted, false)
  assert.equal(f.state.savedCourseId, '')
  assert.deepEqual(f.destinations, [])
})

test('组件卸载后保存回执不能导航或标记新页面已保存', async () => {
  let finish
  const f = await courseForm({ createCourse: async () => new Promise(resolve => { finish = resolve }) })
  const saving = f.state.submit()
  f.unmount()
  finish({ code: 0, data: { courseId: '5330' } }); await saving
  assert.deepEqual(f.destinations, [])
  assert.equal(f.dirty(), true)
  assert.equal(f.state.saveCompleted, false)
})


test('旧保存收尾不能解除新课程提交锁，旧读取失败不能污染新草稿', async () => {
  let oldFinish, newFinish, rejectRead
  const f = await courseForm({ updateCourse: async () => new Promise(resolve => { oldFinish = resolve }), createCourse: async () => new Promise(resolve => { newFinish = resolve }), getCourse: async () => new Promise((_, reject) => { rejectRead = reject }) }, { editId: '5330' })
  const oldSaving = f.state.submit()
  await f.switchCourse('')
  f.state.form.courseCode = 'NEW101'; f.state.form.courseName = '新课程'
  const newSaving = f.state.submit()
  oldFinish({ code: 0, data: { courseId: '5331' } }); await oldSaving
  assert.equal(f.state.submitting, true)
  assert.deepEqual(f.destinations, [])
  newFinish({ code: 0, data: { courseId: '5332' } }); await newSaving
  assert.deepEqual(f.destinations, ['/admin/academic-affairs/courses/5332'])
  const reading = f.switchCourse('5333')
  await f.switchCourse('')
  f.state.form.courseName = '保留的新草稿'
  rejectRead(new Error('旧读取失败')); await reading
  assert.equal(f.state.form.courseName, '保留的新草稿')
  assert.equal(f.state.formError, '')
  assert.equal(f.state.loading, false)
})

test('保存后等待视图更新期间切换对象，不能启动旧档案导航', async () => {
  const f = await courseForm({ updateCourse: async () => ({ code: 0, data: { courseId: '5331' } }) }, { editId: '5330' })
  const render = f.state.$nextTick
  let finishTick
  f.state.$nextTick = () => new Promise(resolve => { finishTick = resolve })
  const saving = f.state.submit()
  await Promise.resolve()
  f.state.$nextTick = render
  await f.switchCourse('')
  finishTick(); await saving
  assert.deepEqual(f.destinations, [])
  assert.equal(f.state.saveCompleted, false)
})


test('课程权威回执负责人姓名通过正式回显扩展点展示，远程搜索仍保持原适配器', async () => {
  let searches = 0, resolves = 0
  const f = await courseForm({ getCourse: async () => ({ code: 0, data: { courseCode: 'OLD101', courseName: '课程', credit: 2, ownerTeacherId: '9007199254740993', ownerTeacherName: '验收负责人' } }) })
  f.state.appPickerAdapters = { teacher: { search: async () => { searches++; return [] }, resolve: async value => { resolves++; return { value, label: '其他授权教师' } } } }
  await f.switchCourse('5330')
  const page = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaCourseFormView.vue'), 'utf8')
  let bound
  await renderToString(createSSRApp({ components: { AppTeacherPicker: { inheritAttrs: false, props: ['modelValue', 'resolveByValue'], render() { bound = this.$props; return '' } } }, data: () => ({ form: f.state.form, ownerTeacherResolver: f.state.ownerTeacherResolver, courseEpoch: f.state.courseEpoch, submitting: f.state.submitting, saveCompleted: f.state.saveCompleted }), render: compile(page.match(/<AppTeacherPicker\b[^>]*\/>/)[0]) }))
  assert.equal(typeof bound.resolveByValue, 'function')
  const option = await bound.resolveByValue(bound.modelValue)
  assert.deepEqual(option, { value: '9007199254740993', label: '验收负责人' })
  assert.equal(resolves, 0)
  const remoteSource = fs.readFileSync(path.join(root, 'src/components/common/picker/AppRemoteSelect.vue'), 'utf8')
  const remote = new Function(remoteSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default', 'return'))()
  const selected = { ...remote.data(), modelValue: bound.modelValue, options: [], multiple: false, resolveByValue: bound.resolveByValue }
  for (const [name, method] of Object.entries(remote.methods)) selected[name] = method.bind(selected)
  for (const [name, getter] of Object.entries(remote.computed)) Object.defineProperty(selected, name, { get: () => getter.call(selected) })
  await selected.hydrateSelected()
  assert.equal(selected.singleLabel, '验收负责人')
  const entitySource = fs.readFileSync(path.join(root, 'src/components/common/picker/entityPickers.js'), 'utf8').replace(/^import.*$/gm, '').replace(/export const /g, 'const ')
  const teacher = new Function('h', 'AppRemoteSelect', entitySource + '; return AppTeacherPicker')((component, props) => ({ component, props }), {})
  const props = teacher.render.call({ appPickerAdapters: f.state.appPickerAdapters, options: [], query: {}, modelValue: bound.modelValue, resolveByValue: bound.resolveByValue, $attrs: {}, $emit() {} }).props
  await props.remoteSearch('验收')
  assert.equal(searches, 1)
  assert.equal((await props.resolveByValue('234283')).label, '其他授权教师')
  assert.equal(resolves, 1)
  const oldResolver = bound.resolveByValue
  await f.switchCourse('')
  assert.equal(await oldResolver('9007199254740993'), undefined)
  assert.equal(f.state.form.ownerTeacherId, '')
})


test('三业务选择器保存中及成功留页禁用交互，失败后恢复编辑', async () => {
  const page = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaCourseFormView.vue'), 'utf8')
  const remoteSource = fs.readFileSync(path.join(root, 'src/components/common/picker/AppRemoteSelect.vue'), 'utf8')
  const remote = new Function(remoteSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default', 'return'))()
  remote.render = compile(remoteSource.slice(remoteSource.indexOf('<template>') + 10, remoteSource.lastIndexOf('</template>', remoteSource.indexOf('<script>'))))
  const entitySource = fs.readFileSync(path.join(root, 'src/components/common/picker/entityPickers.js'), 'utf8').replace(/^import.*$/gm, '').replace(/export const /g, 'const ')
  const pickers = new Function('h', 'AppRemoteSelect', entitySource + '; return { AppTeacherPicker, AppCollegePicker, AppMajorPicker }')(h, remote)
  let finish
  const f = await courseForm({ createCourse: async () => new Promise(resolve => { finish = resolve }) }, { navigationFails: true })
  const inspect = async locked => {
    for (const name of Object.keys(pickers)) {
      const binding = page.match(new RegExp('<' + name + '\\b[^>]*\\/>'))[0]
      const html = await renderToString(createSSRApp({ components: pickers, data: () => f.state, render: compile(binding) }))
      assert.equal(/class="[^"]*is-disabled/.test(html), locked, name)
      assert.equal(/\sinert(?:=""|\s|>)/.test(html), locked, name + '整棵控件阻止交互，包含已打开选项')
      const interactive = { ...remote.data(), disabled: /class="[^"]*is-disabled/.test(html), loadOnOpen: false }
      remote.methods.toggleOpen.call(interactive)
      assert.equal(interactive.open, !locked, name + '正常点击开关')
    }
  }
  await inspect(false)
  const rejected = f.state.submit()
  await inspect(true)
  finish({ code: 1, message: '保存失败' }); await rejected
  await inspect(false)
  const accepted = f.state.submit()
  await inspect(true)
  finish({ code: 0, data: { courseId: '5330' } }); await accepted
  assert.equal(f.state.saveCompleted, true)
  await inspect(true)
})
