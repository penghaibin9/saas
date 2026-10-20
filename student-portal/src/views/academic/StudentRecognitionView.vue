<template>
  <div data-academic-page class="sp-page academic-prototype recognition-page">
    <AcademicPrototypeHeader :title="applying ? '认定申请与材料' : '成绩认定'" group="培养与毕业" :object="applying" description="核对校外学习成果与目标课程，跟踪学校认定。" :loading="loading || submitting" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人认定记录…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack"><AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="applying"><AcademicPrototypeSteps /><section class="card"><header class="card-head"><h2>填写认定对象与事由</h2></header><form class="card-body" @submit.prevent="submit"><div class="form-grid">
        <label class="field full"><span class="req">查找正式目标课程</span><div class="course-search"><input v-model.trim="courseKeyword" class="input" maxlength="80" placeholder="输入课程代码或课程名称" @keyup.enter.prevent="loadCourses(1)" /><button class="btn" type="button" :disabled="courseLoading" @click="loadCourses(1)">{{ courseLoading ? '查询中…' : '查询课程' }}</button></div></label>
        <label class="field"><span class="req">正式目标课程</span><select v-model="form.targetCourseId" :disabled="courseLoading || !courses.length" @change="onCoursePicked"><option value="">请选择学校正式课程</option><option v-for="course in courses" :key="course.courseId" :value="String(course.courseId)">{{ course.courseCode }} · {{ course.courseName }} · 版本 {{ course.version }}</option></select><small v-if="courseError" class="field-error">{{ courseError }}</small><small v-else-if="courseTotal > courses.length">已显示前 {{ courses.length }} / {{ courseTotal }} 门，请输入关键词精确查询。</small></label><label class="field"><span class="req">来源学习成果</span><input v-model.trim="form.sourceCourseName" class="input" maxlength="100" placeholder="填写来源课程或学习成果" /></label>
        <label class="field"><span class="req">来源成绩</span><input v-model="form.sourceScore" class="input" type="number" min="60" max="100" step="1" placeholder="60-100整数" /></label><label class="field"><span>来源学分</span><input v-model="form.sourceCredit" class="input" type="number" min="0" max="50" step="0.5" placeholder="按材料填写" /></label><label class="field full"><span class="req">申请说明</span><textarea v-model.trim="form.reason" maxlength="500" /></label>
        </div><div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>目标课程来自学校正式课程候选；佐证材料要求仍以教务老师核对为准。</span></div><footer class="form-foot"><button class="btn" type="button" @click="applying = false">返回认定记录</button><button class="btn primary" :disabled="!canSubmit || submitting">提交认定申请</button></footer></form></section></template>
      <template v-else><div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>申请不改变正式成绩；佐证仅使用校内文件绑定，不接收任意外部链接。</span></div><div class="wide-action"><div><h2>校外学习成果认定</h2><p>先选择目标课程，再核对适用材料。</p></div><button class="btn primary" @click="applying = true">发起认定</button></div>
        <section class="card"><header class="card-head"><h2>我的申请</h2></header><div class="card-body"><p v-if="!records.length" class="muted">暂无本人认定申请。</p><div v-for="record in records" :key="record.recognitionId || record.id" class="taskline"><div class="grow"><strong>{{ record.targetCourseName || record.courseName || '本人认定申请' }}</strong><small>来源：{{ record.sourceCourseName || '未提供' }} · 审核时间 {{ dateTime(record.reviewedAt) }}</small><small v-if="record.reviewReason || record.reviewNote">{{ record.reviewReason || record.reviewNote }}</small></div><span class="tag" :class="record.status === 'APPROVED' ? 'green' : 'amber'">{{ statusText(record.status) }}</span></div></div></section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'

import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'recognition')
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const applying = ref(false)
const records = ref([])
const courses = ref([])
const courseKeyword = ref('')
const courseLoading = ref(false)
const courseError = ref('')
const courseTotal = ref(0)
const receipt = ref(null)
const receiptTone = ref('success')
const uncertainCommandKey = ref('')
const form = reactive({ sourceCourseName: '', targetCourseId: '', targetCourseName: '', sourceScore: '', sourceCredit: '', reason: '' })
const currentCommandKey = computed(() => `${String(form.targetCourseId)}:${String(form.sourceCourseName).trim()}:${String(form.sourceScore)}:${String(form.reason).trim()}`)
const canSubmit = computed(() => form.sourceCourseName && form.targetCourseId && form.targetCourseName && form.reason && !uncertainCommandKey.value && Number.isInteger(Number(form.sourceScore)) && Number(form.sourceScore) >= 60 && Number(form.sourceScore) <= 100)
const rowsOf = (data) => Array.isArray(data) ? data : (data?.items || data?.list || [])
const dateTime = (value) => String(value || '').slice(0, 16).replace('T', ' ') || '—'
function statusText(value) { return ({ SUBMITTED: '已提交', PENDING: '待审核', APPROVED: '已通过', REJECTED: '未通过', RETURNED: '已退回' })[String(value || '').toUpperCase()] || value || '待确认' }
function onCoursePicked() {
  const selected = courses.value.find((item) => String(item.courseId) === String(form.targetCourseId))
  form.targetCourseName = selected?.courseName || ''
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommand() {
  const reference = guard.pendingCommands().find((item) => item.action === 'SUBMIT_RECOGNITION')
  uncertainCommandKey.value = reference ? `pending:${reference.objectId}` : ''
  if (!reference) return
  const formal = reference.ackId ? records.value.find((row) => String(row.recognitionId || row.id || '') === reference.ackId && String(row.targetCourseId || '') === reference.objectId) : null
  if (formal && guard.completePersistentCommand(reference)) {
    receiptTone.value = 'success'
    receipt.value = academicReceipt({ title: '原成绩认定申请已通过正式记录确认', object: formal.targetCourseName || formal.courseName || '原目标课程', status: statusText(formal.status), operatedAt: formal.createdAt || formal.submittedAt, next: '请在本页跟踪学校审核结果。', relatedTo: '/academic/grades', relatedLabel: '查看正式成绩' })
    uncertainCommandKey.value = ''
  } else {
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: '原成绩认定申请结果待确认', object: '原目标课程', status: reference.ackId ? formal ? '正式记录已读到，但本地待确认引用未能安全清理' : '尚未读取到原回执对应的本人记录' : '原提交未取得服务端回执编号', next: '本页只会刷新本人正式记录，不会自动再次提交。' })
  }
}
async function loadCourses(page = 1) {
  courseLoading.value = true; courseError.value = ''
  const keyword = courseKeyword.value
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicRecognitionCourses({ keyword, page, pageSize: 100 }), 'courses')
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    courses.value = []; courseTotal.value = 0; courseError.value = academicErrorMessage(read.error, '正式课程读取失败，请重试'); courseLoading.value = false
    return false
  }
  courses.value = rowsOf(read.value)
  courseTotal.value = Number(read.value?.total ?? courses.value.length)
  if (form.targetCourseId && !courses.value.some((item) => String(item.courseId) === String(form.targetCourseId))) {
    form.targetCourseId = ''; form.targetCourseName = ''
  } else onCoursePicked()
  courseLoading.value = false
  return true
}
async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => Promise.all([
    refreshRecords(), courses.value.length ? Promise.resolve(true) : loadCourses(1)
  ]), 'page')
  if (read.stale) return false
  loading.value = false
  return read.ok && read.value[0].ok
}
async function refreshRecords() {
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicRecognition(), 'records')
  if (read.stale) return { ok: false }
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') clearSensitive(read.error)
    else error.value = academicErrorMessage(read.error, '认定记录读取失败，请稍后重试')
    return { ok: false }
  }
  const rows = rowsOf(read.value)
  records.value = rows
  reconcilePersistentCommand()
  return { ok: true, rows }
}
async function submit() {
  if (!canSubmit.value || submitting.value) return
  const payload = Object.freeze({ sourceCourseName: form.sourceCourseName.trim(), targetCourseId: String(form.targetCourseId), targetCourseName: form.targetCourseName, sourceScore: Number(form.sourceScore), ...(form.sourceCredit === '' ? {} : { sourceCredit: Number(form.sourceCredit) }), ...(form.reason ? { reason: form.reason.trim() } : {}) })
  const object = `${payload.sourceCourseName} → ${payload.targetCourseName}`
  const command = guard.beginCommand({ key: currentCommandKey.value, payload, object })
  if (!await systemConfirm({ title: '确认成绩认定申请', message: `确认提交“${command.object}”成绩认定申请？`, confirmText: '提交认定申请' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'SUBMIT_RECOGNITION', objectId: command.payload.targetCourseId })
  if (!persistent) {
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '认定申请未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' })
    return
  }
  submitting.value = true
  try {
    const result = await portalApi.academicRecognitionSubmit(command.payload)
    if (!guard.isCurrentCommand(command)) return
    uncertainCommandKey.value = command.key
    const acknowledged = guard.rememberPersistentAck(persistent, result?.recognitionId)
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '正在读取本人正式认定记录', next: '确认前不要重复提交。' })
    const formalRead = await refreshRecords()
    if (!guard.isCurrentCommand(command) || !formalRead.ok) return
    const formalRows = formalRead.rows
    const formal = acknowledged?.ackId
      ? formalRows.find((row) => String(row.recognitionId || row.id) === acknowledged.ackId)
      : null
    const sameSource = formal && (!formal.sourceCourseName || String(formal.sourceCourseName).trim() === command.payload.sourceCourseName)
    if (formal && String(formal.targetCourseId) === command.payload.targetCourseId && sameSource && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'; receipt.value = academicReceipt({ title: '成绩认定申请已提交并核对', object: command.object, status: statusText(formal.status), operatedAt: formal.createdAt || formal.submittedAt, next: '请在本页跟踪审核；通过后再到成绩查询核对正式成绩。', relatedTo: '/academic/grades', relatedLabel: '查看正式成绩' })
      uncertainCommandKey.value = ''
      if (currentCommandKey.value === command.key) {
        Object.assign(form, { sourceCourseName: '', targetCourseId: '', targetCourseName: '', sourceScore: '', sourceCredit: '', reason: '' })
        applying.value = false
        markStudentAcademicFormClean()
      }
    } else {
      uncertainCommandKey.value = command.key
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '尚未读取到匹配的本人认定记录', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    const kind = studentAcademicWriteErrorKind(e)
    if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
    if (kind === 'network' || kind === 'conflict') uncertainCommandKey.value = command.key
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: kind === 'conflict' ? '业务事实已变化' : kind === 'network' ? '提交结果待确认' : '申请未提交', object: command.object, status: kind === 'network' ? '待服务器记录确认' : '未完成', next: academicErrorMessage(e, '请核对填写内容后重试。') })

    if (kind === 'network' || kind === 'conflict') {
      try {
        await refreshRecords()
      } catch (readError) {
        if (academicErrorKind(readError) === 'forbidden') clearSensitive(readError)
      }
    }
  } finally { if (guard.isCurrentCommand(command)) submitting.value = false }
}
function clearSensitive(e) {
  guard.invalidate()
  records.value = []; courses.value = []; courseTotal.value = 0; Object.assign(form, { sourceCourseName: '', targetCourseId: '', targetCourseName: '', sourceScore: '', sourceCredit: '', reason: '' })
  receipt.value = null
  loading.value = false; courseLoading.value = false; submitting.value = false
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.form-notice{margin-top:14px}.course-search{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.field-error{color:#b91c1c}@media(max-width:640px){.course-search{grid-template-columns:1fr}}</style>
