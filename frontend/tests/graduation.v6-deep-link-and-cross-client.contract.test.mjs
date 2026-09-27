import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const here = dirname(fileURLToPath(import.meta.url))
const read = (path) => readFileSync(resolve(here, '..', path), 'utf8')

const shell = read('src/modules/graduation/views/_shared/GraduationFormPageShell.vue')
const batch = read('src/modules/graduation/views/GraduationBatchFormView.vue')
const studentForm = read('src/modules/graduation/views/GraduationStudentFormView.vue')
const topic = read('src/modules/graduation/views/TopicLibFormView.vue')
const defense = read('src/modules/graduation/views/DefenseGroupFormView.vue')
const defenseGradeForm = read('src/modules/graduation/views/GraduationDefenseGradeFormView.vue')
const reviewWorkspace = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
const pdfAdapter = read('src/components/file/viewer/adapters/PdfViewerAdapter.vue')
const studentFeedback = read('../student-portal/src/views/graduation/GraduationFeedbackResubmitView.vue')
const studentMini = read('../miniapp/src/pages/student/graduation/index.vue')
const teacherMini = read('../miniapp/src/pages/teacher/graduation-guide/index.vue')
const teacherCountTruth = read('../miniapp/src/services/graduationTeacherCountTruth.js')
const miniFileSdk = read('../miniapp/src/services/fileSdk.js')

function topicForm(roleCode, api) {
  const { descriptor, errors } = parse(topic)
  assert.deepEqual(errors, [])
  const source = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component =')
  const actor = { currentRoleCode: roleCode }
  const sandbox = {
    gdTopicApi: api,
    currentUserFromToken: () => actor,
    toast: { success() {}, info() {} },
    GD_TOPIC_CATEGORY: [], GD_TOPIC_DIFFICULTY: [],
    GraduationFormPageShell: {}, ErrorState: {}, LoadingState: {},
    AppGraduationDesignBatchPicker: {}, AppGraduationMentorPicker: {}, AppSelect: {}, AppTemplateChips: {}
  }
  vm.runInNewContext(source, sandbox)
  const component = sandbox.component
  const instance = {
    ...component.data(),
    ctx: { ctxKey: roleCode, currentRole: { roleCode: roleCode === 'GD_MENTOR' ? 'SCHOOL_ADMIN' : 'GD_MENTOR' } },
    $route: { params: {}, query: {} },
    $router: { resolve: () => ({ fullPath: '/admin/graduation/topics' }), push: async () => {} }
  }
  for (const [key, getter] of Object.entries(component.computed)) {
    Object.defineProperty(instance, key, { get: () => getter.call(instance) })
  }
  for (const [key, method] of Object.entries(component.methods)) instance[key] = method.bind(instance)
  return { instance, actor }
}

test('deep-link shell keeps work context and safe return while using an in-flow sticky footer', () => {
  assert.match(shell, /layout === 'inline'/)
  assert.match(shell, /\$slots\.context/)
  assert.match(shell, /\$slots\.aside/)
  assert.match(shell, /aria-label="办理条件与下一步"/)
  assert.match(shell, /safeReturnTo/)
  assert.match(shell, /returnTo/)
  assert.match(shell, /:disabled="busy"/)
  assert.match(shell, /正在提交，请勿切换页面或重复点击/)
  assert.match(shell, /gd-form-footer--sticky/)
  assert.match(shell, /position: sticky/)
  assert.doesNotMatch(shell, /AppStickyFooter/)
  assert.match(shell, /gd-form-body--aside/)
})

test('batch deep link stays canonical while exposing accessible labels and a compact next-step disclosure', () => {
  for (const marker of ['批次身份', '实施边界', '保存前检查', '保存后的下一步']) assert.match(batch, new RegExp(marker))
  for (const id of ['gd-batch-name', 'gd-batch-no', 'gd-grade-year', 'gd-academic-year', 'gd-planned-count', 'gd-college-scope', 'gd-batch-remark']) {
    assert.match(batch, new RegExp(`id="${id}"`))
  }
  assert.match(batch, /for="gd-planned-count"/)
  assert.match(batch, /aria-describedby="gd-planned-count-hint"/)
  assert.match(batch, /graduationBatchApi\.createBatch\(snapshot\.body\)/)
  assert.match(batch, /graduationBatchApi\.updateBatch\(snapshot\.id, snapshot\.body\)/)
  assert.match(batch, /commandSnapshot/)
  assert.match(batch, /freezeSnapshot/)
  assert.match(batch, /beforeRouteLeave/)
  assert.match(batch, /next\(false\)/)
  assert.match(batch, /validateRange/)
  assert.doesNotMatch(batch, /跨端影响/)
})

test('student create deep link uses the school master and keeps the canonical three-field API contract', () => {
  for (const marker of ['选择学校学生主档', '建立批次与指导关系', '保存前检查', '建档后的下一步']) assert.match(studentForm, new RegExp(marker))
  assert.match(studentForm, /AppGraduationCandidateStudentPicker/)
  assert.match(studentForm, /AppGraduationDesignBatchPicker/)
  assert.match(studentForm, /AppGraduationMentorPicker/)
  assert.match(studentForm, /studentId: target\.studentId/)
  assert.match(studentForm, /advisorName: target\.advisorName \|\| undefined/)
  assert.match(studentForm, /if \(target\.batchId\) body\.batchId = target\.batchId/)
  assert.match(studentForm, /gdStudentApi\.createStudent\(body\)/)
  assert.match(studentForm, /safeReturnTo/)
  assert.match(studentForm, /beforeRouteLeave/)
  assert.match(studentForm, /next\(false\)/)
  assert.doesNotMatch(studentForm, /createStudentProfile|毕业资格.*(?:写入|修改)/)
})

test('topic application deep link explains the real review handoff without bypassing topic APIs', () => {
  for (const marker of ['题目身份', '指导与适用范围', '完成标准', '保存方式', '保存后的真实流转']) assert.match(topic, new RegExp(marker))
  assert.match(topic, /AppGraduationMentorPicker/)
  assert.match(topic, /gdTopicApi\.createTopic\(snapshot\.body\)/)
  assert.match(topic, /gdTopicApi\.updateTopic\(snapshot\.id, snapshot\.body\)/)
  assert.match(topic, /commandSnapshot/)
  assert.match(topic, /beforeRouteLeave/)
  assert.match(topic, /submitReview/)
  assert.match(topic, /审核通过后才进入选题轮次/)
})

test('mentor topic form self-binds without a picker or client-supplied advisor, while manager keeps selection', async () => {
  const { descriptor } = parse(topic)
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'TopicLibFormView.vue', id: 'topic-form' }).errors, [])
  assert.match(descriptor.template.content, /v-if="mentorSelfBound"[\s\S]*AppGraduationMentorPicker v-else/)
  const mentorBodies = []
  let release
  const pending = new Promise(resolve => { release = resolve })
  const mentor = topicForm('GD_MENTOR', {
    createTopic: async body => { mentorBodies.push(body); await pending; return { code: 0, data: { id: 'T1' } } },
    updateTopic: async () => { throw Error('unexpected update') }
  }).instance
  mentor.form.title = '真实导师申报题目'
  mentor.form.advisorName = '前页残留的其他导师'
  assert.equal(mentor.mentorSelfBound, true)
  assert.equal(mentor.advisorReady, true)
  assert.equal(mentor.completionCount, 2)
  const saving = mentor.submitForm()
  await mentor.submitForm()
  assert.equal(mentorBodies.length, 1)
  assert.equal(Object.hasOwn(mentorBodies[0], 'advisorName'), false)
  mentor.form.title = '保存中改动不能覆盖快照'
  assert.equal(mentorBodies[0].title, '真实导师申报题目')
  release()
  await saving

  const managerBodies = []
  const manager = topicForm('SCHOOL_ADMIN', {
    createTopic: async body => { managerBodies.push(body); return { code: 0, data: { id: 'T2' } } },
    updateTopic: async () => { throw Error('unexpected update') }
  }).instance
  manager.form.title = '管理员申报题目'
  assert.equal(manager.mentorSelfBound, false)
  assert.equal(manager.advisorReady, false)
  manager.form.advisorName = '管理员选择的导师'
  assert.equal(manager.advisorReady, true)
  await manager.submitForm()
  assert.equal(managerBodies[0].advisorName, '管理员选择的导师')
})

test('defense group deep link separates schedule, real identities and students, then rereads server truth', () => {
  for (const marker of ['分组与排期', '答辩职责', '学生分配', '发布前明显缺口', '职责分离', '正式发布']) assert.match(defense, new RegExp(marker))
  assert.match(defense, /AppGraduationMentorPicker/)
  assert.match(defense, /graduationApi\.createDefenseGroup\(snapshot\.body\)/)
  assert.match(defense, /graduationApi\.updateDefenseGroup\(snapshot\.groupId, snapshot\.body\)/)
  assert.match(defense, /graduationApi\.assignDefenseStudents\(snapshot\.groupId, snapshot\.studentIds\)/)
  assert.match(defense, /graduationApi\.unassignDefenseStudents\(snapshot\.groupId, \[snapshot\.studentId\]\)/)
  assert.match(defense, /graduationApi\.getDefenseGroupDetail\(this\.groupId\)/)
  assert.match(defense, /eligibleRequestToken/)
  assert.match(defense, /preflightGaps/)
  assert.match(defense, /beforeRouteLeave/)
  assert.match(defense, /评分与秘书确认不能互相代替/)
})

test('defense score binds the judge to the authenticated actor and provides accessible fields', () => {
  assert.match(defenseGradeForm, /getAuthContext/)
  assert.match(defenseGradeForm, /this\.actorName = String\(auth\.displayName \|\| auth\.username \|\| ''\)/)
  assert.match(defenseGradeForm, /当前登录评委/)
  assert.match(defenseGradeForm, /评分人来自登录身份与答辩组席位，不能在页面中修改/)
  assert.doesNotMatch(defenseGradeForm, /key: 'judgeName'/)
  assert.match(defenseGradeForm, /judgeName: snapshot\.actorName/)
  assert.match(defenseGradeForm, /fieldId\(field\)/)
  assert.match(defenseGradeForm, /:for="fieldId\(field\)"/)
  assert.match(defenseGradeForm, /:aria-describedby="field\.hint \? hintId\(field\) : undefined"/)
})

test('teacher PC thesis review is bound to a real canonical FileVersion and actual PDF canvas adapter', () => {
  assert.match(reviewWorkspace, /data-testid="review-command-contract"/)
  assert.match(reviewWorkspace, /canonicalFileVersionId/)
  assert.match(reviewWorkspace, /expectedVersion/)
  assert.match(reviewWorkspace, /FileEvidencePanel/)
  assert.match(reviewWorkspace, /AppDocumentViewer/)
  assert.match(reviewWorkspace, /reviewReady && !versionConflict/)
  assert.match(reviewWorkspace, /<details class="gd-review-workspace__evidence">/)
  assert.match(pdfAdapter, /data-preview-adapter="pdf"/)
  assert.match(pdfAdapter, /<canvas/)
  assert.match(pdfAdapter, /pdfjsLib\.getDocument/)
  assert.match(pdfAdapter, /page\.render/)
})

test('student PC keeps the teacher-reviewed frozen version and submits a new thesis version instead of overwriting history', () => {
  assert.match(studentFeedback, /本次意见对应冻结版/)
  assert.match(studentFeedback, /FileVersion \{\{ actionable\.reviewedFile\.fileVersionId \}\}/)
  assert.match(studentFeedback, /SHA-256/)
  assert.match(studentFeedback, /重新提交不会覆盖老师评阅过的旧版本/)
  assert.match(studentFeedback, /graduationW75Api\.submitFinal/)
  assert.match(studentFeedback, /expectedVersion: materialVersion/)
  assert.match(studentFeedback, /StudentDocumentViewer/)
  assert.match(studentFeedback, /issueTicket\(file\.fileId, 'preview'\)/)
})

test('teacher miniapp locks an exact batch task before previewing the same FileVersion', () => {
  assert.match(teacherMini, /成果待批阅/)
  assert.match(teacherMini, /materialVersion/)
  assert.match(teacherMini, /fileVersionId/)
  assert.match(teacherMini, /openVersion/)
  assert.match(teacherMini, /revalidatePreviewContext/)
  assert.match(teacherCountTruth, /currentPageOptions\(\)/)
  for (const key of ['batchId', 'kind', 'gdStudentId', 'recordId', 'materialVersion', 'fileVersionId']) assert.match(teacherCountTruth, new RegExp(key))
  assert.match(teacherCountTruth, /setTeacherGraduationBatch/)
  assert.match(teacherCountTruth, /responseBatchId !== String\(selected\.id\)/)
  assert.match(teacherCountTruth, /指定的毕业设计待办不在当前批次或当前角色数据范围内/)
  assert.match(miniFileSdk, /openDocument/)
  assert.match(miniFileSdk, /ticketPath/)
  assert.match(miniFileSdk, /realDownload\(`\$\{openPath\}\?ticket=/)
})

test('student miniapp keeps high-frequency status and hands large thesis upload to student PC', () => {
  assert.match(studentMini, /毕业设计/)
  assert.match(studentMini, /学生\s*PC/)
  assert.match(studentMini, /论文/)
  assert.match(studentMini, /material/)
  assert.match(studentMini, /fileSdk\.upload/)
  assert.match(studentMini, /onPullDownRefresh/)
  assert.match(studentMini, /(?:正式|大型)论文[^\n<]*学生\s*PC/)
})
