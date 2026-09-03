import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const read = (path) => readFileSync(resolve(here, '..', path), 'utf8')

const shell = read('src/modules/graduation/views/_shared/GraduationFormPageShell.vue')
const batch = read('src/modules/graduation/views/GraduationBatchFormView.vue')
const topic = read('src/modules/graduation/views/TopicLibFormView.vue')
const defense = read('src/modules/graduation/views/DefenseGroupFormView.vue')
const reviewWorkspace = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
const pdfAdapter = read('src/components/file/viewer/adapters/PdfViewerAdapter.vue')
const studentFeedback = read('../student-portal/src/views/graduation/GraduationFeedbackResubmitView.vue')
const studentMini = read('../miniapp/src/pages/student/graduation/index.vue')
const teacherMini = read('../miniapp/src/pages/teacher/graduation-guide/index.vue')
const miniFileSdk = read('../miniapp/src/services/fileSdk.js')

test('deep-link shell exposes real work context, completion rail and safe return while commands are locked', () => {
  assert.match(shell, /layout === 'inline'/)
  assert.match(shell, /\$slots\.context/)
  assert.match(shell, /\$slots\.aside/)
  assert.match(shell, /办理条件与下一步/)
  assert.match(shell, /safeReturnTo/)
  assert.match(shell, /returnTo/)
  assert.match(shell, /:disabled="busy"/)
  assert.match(shell, /正在提交，请勿切换页面或重复点击/)
  assert.match(shell, /AppStickyFooter/)
  assert.match(shell, /gd-form-body--aside/)
})

test('batch deep link is a guided business workflow and still writes the canonical batch APIs', () => {
  for (const marker of ['批次身份', '实施边界', '保存前检查', '保存后的真实流程', '跨端影响']) {
    assert.match(batch, new RegExp(marker))
  }
  assert.match(batch, /graduationBatchApi\.createBatch\(snapshot\.body\)/)
  assert.match(batch, /graduationBatchApi\.updateBatch\(snapshot\.id, snapshot\.body\)/)
  assert.match(batch, /commandSnapshot/)
  assert.match(batch, /freezeSnapshot/)
  assert.match(batch, /beforeRouteLeave/)
  assert.match(batch, /next\(false\)/)
  assert.match(batch, /validateRange/)
})

test('topic application deep link explains the real review handoff without bypassing topic APIs', () => {
  for (const marker of ['题目身份', '指导与适用范围', '完成标准', '保存方式', '保存后的真实流转']) {
    assert.match(topic, new RegExp(marker))
  }
  assert.match(topic, /AppGraduationMentorPicker/)
  assert.match(topic, /gdTopicApi\.createTopic\(snapshot\.body\)/)
  assert.match(topic, /gdTopicApi\.updateTopic\(snapshot\.id, snapshot\.body\)/)
  assert.match(topic, /commandSnapshot/)
  assert.match(topic, /beforeRouteLeave/)
  assert.match(topic, /submitReview/)
  assert.match(topic, /审核通过后才进入选题轮次/)
})

test('defense group deep link separates schedule, real identities and students, then rereads server truth', () => {
  for (const marker of ['分组与排期', '答辩职责', '学生分配', '发布前明显缺口', '职责分离', '正式发布']) {
    assert.match(defense, new RegExp(marker))
  }
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

test('teacher PC thesis review is bound to a real canonical FileVersion and actual PDF canvas adapter', () => {
  assert.match(reviewWorkspace, /data-testid="review-command-contract"/)
  assert.match(reviewWorkspace, /canonicalFileVersionId/)
  assert.match(reviewWorkspace, /expectedVersion/)
  assert.match(reviewWorkspace, /FileEvidencePanel/)
  assert.match(reviewWorkspace, /AppDocumentViewer/)
  assert.match(reviewWorkspace, /reviewReady && !versionConflict/)
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

test('teacher miniapp reads the same FileVersion, uses an authorized ticket and revalidates after preview', () => {
  assert.match(teacherMini, /成果待批阅/)
  assert.match(teacherMini, /开始批阅成果/)
  assert.match(teacherMini, /materialVersion/)
  assert.match(teacherMini, /fileVersionId/)
  assert.match(teacherMini, /mobile\/graduation\/material-center\/files/)
  assert.match(teacherMini, /ticket/)
  assert.match(teacherMini, /openVersion/)
  assert.match(teacherMini, /revalidatePreviewContext/)
  assert.match(teacherMini, /版本已变化/)
  assert.match(miniFileSdk, /openDocument/)
  assert.match(miniFileSdk, /ticketPath/)
  assert.match(miniFileSdk, /realDownload\(`\$\{openPath\}\?ticket=/)
})

test('student miniapp keeps high-frequency status and deliberately hands large thesis upload to student PC', () => {
  assert.match(studentMini, /毕业设计/)
  assert.match(studentMini, /学生PC/)
  assert.match(studentMini, /论文/)
  assert.match(studentMini, /material/)
  assert.match(studentMini, /fileSdk\.upload/)
  assert.match(studentMini, /onPullDownRefresh/)
  assert.match(studentMini, /大型论文、作品或源代码请到学生 PC 上传/)
})
