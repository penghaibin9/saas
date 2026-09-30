<template>
  <div data-academic-page class="sp-page academic-prototype recheck-page">
    <AcademicPrototypeHeader :title="applying ? '成绩复查申请' : '成绩复查'" group="成绩与考试" :object="applying" description="复查本人已发布成绩，跟踪学校核查结果。" :loading="loading || submitting" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人已发布成绩和复查记录…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="applying">
        <AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>{{ currentGrade?.courseName || '选择正式成绩' }} · 本人复查申请</h2></header>
          <form class="card-body" @submit.prevent="submit"><div class="form-grid">
            <label class="field"><span class="req">正式成绩对象</span><select v-model="selectedGradeId"><option value="">请选择已发布成绩</option><option v-for="grade in eligibleGrades" :key="grade.gradeId" :value="String(grade.gradeId)">{{ grade.courseName }} · {{ scoreText(grade.score, grade.passStatus) }}</option></select></label>
            <label class="field full"><span class="req">需核对事项</span><textarea v-model.trim="reason" maxlength="200" placeholder="说明需要核对的问题（至少 5 字，最多 200 字）" /></label>
          </div><div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>只对本人已发布的正式成绩发起。原因至少5个字，申请不会直接修改分数。</span></div><footer class="form-foot"><button class="btn" type="button" @click="applying = false">返回复查记录</button><button class="btn primary" :disabled="!canSubmit || submitting">{{ submitting ? '提交中…' : '提交复查申请' }}</button></footer></form>
        </section>
      </template>
      <template v-else>
        <div class="wide-action"><div><h2>对已发布成绩有疑问？</h2><p>选择本人正式成绩，说明核对原因。</p></div><button class="btn primary" :disabled="!eligibleGrades.length" @click="applying = true">发起复查</button></div>
        <section class="card"><header class="card-head"><h2>我发起的复查</h2></header><div class="card-body">
          <StateBlock v-if="!records.length" type="empty" text="暂无本人复查申请" />
          <article v-for="record in records" :key="record.recheckId || record.id" class="record">
            <div class="row between"><div><h2>{{ record.courseName || '本人正式成绩' }}</h2><small>申请编号 {{ record.recheckId || record.id || '待提供' }} · {{ dateTime(record.createdAt) }}</small></div><span class="tag" :class="record.status === 'ADJUSTED' ? 'green' : 'amber'">{{ statusText(record.status) }}</span></div>
            <dl class="definition"><dt>当前进度</dt><dd>{{ statusText(record.status) }}</dd><dt>需核对事项</dt><dd>{{ record.reason || '未提供' }}</dd><dt>处理结果</dt><dd>{{ record.resultNote || record.reviewNote || record.reply || '以学校受理结果为准' }}</dd></dl>
            <div class="divider"></div><p class="label">复查申请本身不改变正式成绩；更正须经学校正式命令。</p>
          </article>
        </div></section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'
import { createStudentAcademicCommandGuard, exactPositiveDecimalId, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'

import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'recheck')
const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const records = ref([])
const grades = ref([])
const route = useRoute()
const selectedGradeId = ref(String(route.query.gradeId || ''))
const reason = ref('')
const applying = ref(!!route.query.gradeId)
const currentGrade = computed(() => grades.value.find(grade => String(grade.gradeId) === selectedGradeId.value))
const receipt = ref(null)
const receiptTone = ref('success')
const uncertainGradeId = ref('')

const inFlightGradeIds = computed(() => new Set(
  records.value
    .filter((record) => String(record.status || '').toUpperCase() === 'SUBMITTED')
    .map((record) => String(record.acadGradeId || ''))
))
const eligibleGrades = computed(() => grades.value.filter((grade) =>
  exactPositiveDecimalId(grade.gradeId) && !inFlightGradeIds.value.has(exactPositiveDecimalId(grade.gradeId))))
const canSubmit = computed(() =>
  !!exactPositiveDecimalId(selectedGradeId.value) && !uncertainGradeId.value && eligibleGrades.value.some((grade) => exactPositiveDecimalId(grade.gradeId) === selectedGradeId.value) && reason.value.trim().length >= 5 && reason.value.trim().length <= 200)

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records)) || []
}
function scoreText(value, status) {
  const special = { EXEMPT: '免修', EXEMPTED: '免修', DEFERRED: '缓考', ABSENT: '缺考' }
  return special[status] || (value == null || value === '' ? '待确认' : `${value} 分`)
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
function statusText(status) {
  const map = { SUBMITTED: '复查中', UPHELD: '维持原成绩', ADJUSTED: '已调整', REJECTED: '不予受理' }
  return map[String(status || '').toUpperCase()] || status || '待确认'
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommand() {
  const pending = guard.pendingCommands().filter((item) => item.action === 'SUBMIT_RECHECK')
  uncertainGradeId.value = pending[0]?.objectId || ''
  if (!pending.length) return
  const reference = pending[0]
  const formal = reference.ackId ? records.value.find((row) => String(row.recheckId || row.id || '') === reference.ackId && String(row.acadGradeId || row.gradeId || '') === reference.objectId) : null
  const grade = grades.value.find((row) => String(row.gradeId || '') === reference.objectId)
  if (formal && guard.completePersistentCommand(reference)) {
    receiptTone.value = 'success'
    receipt.value = academicReceipt({ title: '原成绩复查申请已通过正式记录确认', object: grade?.courseName || '原正式成绩', status: statusText(formal.status), operatedAt: formal.createdAt || formal.submittedAt, next: '请在本页跟踪复查结果。', relatedTo: '/academic/grades', relatedLabel: '查看正式成绩' })
    uncertainGradeId.value = ''
  } else {
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: '原成绩复查申请结果待确认', object: grade?.courseName || '原正式成绩', status: reference.ackId ? formal ? '正式记录已读到，但本地待确认引用未能安全清理' : '尚未读取到原回执对应的本人记录' : '原提交未取得服务端回执编号', next: '本页只会刷新本人正式记录，不会自动再次提交。' })
  }
}
async function load() {
  // A manual refresh represents a new read of the formal record.  Do not leave the
  // one-time submit receipt on screen with its old status after school review has
  // moved the same application to a terminal state.  In-flight submit verification
  // keeps its receipt because submitting remains true until attribution completes.
  if (!submitting.value) {
    receipt.value = null
    receiptTone.value = 'success'
  }
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => Promise.all([
      portalApi.academicGradeRecheck(),
      portalApi.academicTranscript()
  ]))
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '成绩复查数据读取失败，请稍后重试')
    loading.value = false
    return false
  }
  const [recheckResult, transcriptResult] = read.value
  records.value = rowsOf(recheckResult)
  grades.value = rowsOf(transcriptResult).filter((grade) => exactPositiveDecimalId(grade.gradeId))
  reconcilePersistentCommand()
  if (selectedGradeId.value && !eligibleGrades.value.some((grade) => exactPositiveDecimalId(grade.gradeId) === selectedGradeId.value)) selectedGradeId.value = ''
  loading.value = false
  return true
}
async function submit() {
  if (!canSubmit.value || submitting.value) return
  const draftGradeId = exactPositiveDecimalId(selectedGradeId.value)
  if (!draftGradeId) { error.value = '成绩编号无法准确读取，请刷新正式成绩。'; return }
  const draftReason = reason.value.trim()
  const selectedGrade = eligibleGrades.value.find((grade) => exactPositiveDecimalId(grade.gradeId) === draftGradeId)
  const command = guard.beginCommand({ gradeId: draftGradeId, reason: draftReason, courseName: selectedGrade?.courseName || '当前课程成绩' })
  if (!await systemConfirm({ title: '确认成绩复查申请', message: `确认对“${command.courseName}”的正式成绩提交复查申请？`, confirmText: '提交复查申请' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'SUBMIT_RECHECK', objectId: command.gradeId })
  if (!persistent) {
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: '复查申请未发送', object: command.courseName, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' })
    return
  }
  submitting.value = true
  try {
    const result = await portalApi.academicGradeRecheckSubmit({
      acadGradeId: command.gradeId,
      reason: command.reason
    })
    if (!guard.isCurrentCommand(command)) return
    uncertainGradeId.value = command.gradeId
    const resultId = guard.rememberPersistentAck(persistent, result?.recheckId)?.ackId || ''
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.courseName, status: '正在读取本人正式复查记录', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    // 成功归因只能使用本次 POST 的正式复查编号；历史同成绩/同事由不能证明本次写入成功。
    const formal = resultId
      ? records.value.find((row) => String(row.recheckId) === String(resultId))
      : null
    const sameGrade = formal && String(formal.acadGradeId || formal.gradeId || '') === command.gradeId
    if (sameGrade && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'
      receipt.value = academicReceipt({ title: '成绩复查申请已提交并核对', object: command.courseName, status: statusText(formal.status), operatedAt: formal.createdAt || formal.submittedAt, next: '原正式成绩保持不变，请在本页跟踪复查结果。', relatedTo: '/academic/grades', relatedLabel: '查看正式成绩' })
      if (uncertainGradeId.value === command.gradeId) uncertainGradeId.value = ''
      if ((!selectedGradeId.value || selectedGradeId.value === command.gradeId) && reason.value.trim() === command.reason) { selectedGradeId.value = ''; reason.value = ''; applying.value = false }
      markStudentAcademicFormClean()
    } else {
      uncertainGradeId.value = command.gradeId
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.courseName, status: '尚未读取到匹配的本人复查申请', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    const kind = studentAcademicWriteErrorKind(e)
    if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
    if (kind === 'network' || kind === 'conflict') uncertainGradeId.value = command.gradeId
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: kind === 'network' ? '申请结果待确认' : kind === 'conflict' ? '成绩事实已变化' : '申请未提交', object: command.courseName, status: kind === 'network' ? '待服务器记录确认' : '未完成', next: academicErrorMessage(e, '请核对后重试。') })

    if (kind === 'network' || kind === 'conflict') { const readOk = await load(); if (guard.isCurrentCommand(command) && readOk) { selectedGradeId.value = command.gradeId; reason.value = command.reason } }
  } finally {
    if (guard.isCurrentCommand(command)) submitting.value = false
  }
}

function clearSensitive(e) {
  guard.invalidate()
  records.value = []; grades.value = []; selectedGradeId.value = ''; reason.value = ''
  receipt.value = null
  loading.value = false; submitting.value = false
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.form-notice {margin-top:14px;}.record + .record {border-top:1px solid var(--line);margin-top:18px;padding-top:18px;}.definition{margin:14px 0;}
</style>
