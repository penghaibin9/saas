<template>
  <div data-academic-page class="sp-page academic-prototype level-page">
    <AcademicPrototypeHeader :title="selectedExam ? '等级考试报名确认' : '等级考试'" group="培养与毕业" :object="!!selectedExam" description="核对等级考试项目、报名资格与学校返回的状态。" :loading="loading || !!actingId" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取等级考试与本人报名…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="selectedExam">
        <AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>{{ selectedExam.examName || selectedExam.name }} · 本人报名</h2></header><form class="card-body" @submit.prevent="confirmed && register(selectedExam)">
          <div class="form-grid"><label class="field"><span>考试项目</span><input class="input" :value="selectedExam.examName || selectedExam.name" readonly /></label><label class="field"><span>考试安排</span><input class="input" :value="dateTime(selectedExam.examDate || selectedExam.startAt)" readonly /></label><label class="field full"><span><input v-model="confirmed" class="check" type="checkbox" /> 已核对本人资格和时间安排</span></label></div>
          <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>{{ actionHint(selectedExam) }} 费用：{{ feeText(selectedExam.fee ?? selectedExam.registrationFee) }}。实际报名与取消由学校状态和服务端结果裁决。</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="selectedExamId = ''; confirmed = false">返回等级考试</button><button class="btn primary" :disabled="!confirmed || !!actingId || !canRegister(selectedExam)">{{ actingId ? '提交中…' : '确认本人报名' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <StateBlock v-if="!exams.length" type="empty" text="暂无等级考试项目或本人报名记录" />
        <section v-for="exam in exams.filter(item => item.status !== 'CLOSED' || !item.registration)" :key="examId(exam)" class="card"><header class="card-head"><h2>{{ exam.examName || exam.name || '等级考试' }}</h2></header><div class="card-body">
          <div class="row between"><span class="tag" :class="canRegister(exam) ? 'green' : 'amber'">{{ registrationText(exam) }}</span><small>截至 {{ dateTime(exam.regEnd || exam.registrationEnd || exam.registerEnd) }}</small></div>
          <dl class="definition"><dt>考试安排</dt><dd>{{ dateTime(exam.examDate || exam.startAt) }} · 具体场次以正式安排为准</dd><dt>本人资格</dt><dd>{{ actionHint(exam) }}</dd><dt>费用</dt><dd>{{ feeText(exam.fee ?? exam.registrationFee) }} · 不推断已支付</dd></dl>
          <footer class="form-foot"><button class="btn primary" :disabled="!canRegister(exam) || !!actingId" @click="selectedExamId = examId(exam); confirmed = false">查看并确认报名</button></footer>
        </div></section>
        <section class="card" :aria-label="'我的报名，当前有效 ' + registeredCount + ' 项'"><header class="card-head"><h2>我的报名</h2></header><div class="card-body">
          <p v-if="!personalExams.length" class="muted">暂无已完成报名。提交后将显示学校返回的实际状态。</p>
          <div v-for="exam in personalExams" :key="examId(exam)" class="taskline"><div class="grow"><strong>{{ exam.examName || exam.name }}</strong><small>{{ actionHint(exam) }}</small><small>{{ personalResult(exam) }}</small></div><span class="tag" :class="isRegistered(exam) ? 'green' : 'gray'">{{ registrationText(exam) }}</span><button v-if="canCancel(exam)" class="btn small" :disabled="!!actingId" @click="cancel(exam)">取消报名</button></div>
        </div></section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import { createStudentAcademicCommandGuard, exactPositiveDecimalId, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'

import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'level-exam')
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const data = ref({})
const receipt = ref(null)
const receiptTone = ref('success')
const selectedExamId = ref('')
const confirmed = ref(false)
const pendingExamIds = ref([])
const blockedExamIds = ref([])
let pageIdentity = ''
let actingToken = 0
let actingIdentity = ''
const selectedExam = computed(() => exams.value.find(exam => examId(exam) === selectedExamId.value))
const personalExams = computed(() => exams.value.filter(exam => rawRegistrationStatus(exam)))
const registeredCount = computed(() => exams.value.filter(isRegistered).length)
const exams = computed(() => {
  const value = data.value
  if (Array.isArray(value)) return value
  if (Array.isArray(value.openExams)) {
    const registrations = value.myRegs || []
    const open = value.openExams.map((exam) => ({ ...exam, registration: registrations.find((item) => String(item.examId) === String(exam.examId)) }))
    const closed = registrations.filter((item) => !open.some((exam) => String(exam.examId) === String(item.examId)))
      .map((item) => ({ examId: item.examId, examName: item.examName || '历史等级考试报名', status: 'CLOSED', registration: item }))
    return [...open, ...closed]
  }
  return (value && (value.items || value.list || value.exams)) || []
})

function examId(exam) { return exactPositiveDecimalId(exam?.examId || exam?.id || exam?.levelExamId) || String(exam?.examCode || exam?.examName || '') }
function commandExamId(exam) { return exactPositiveDecimalId(exam?.examId || exam?.id || exam?.levelExamId) }
function registration(exam) { return exam.registration || exam.myRegistration || {} }
function registrationId(exam) { return exactPositiveDecimalId(registration(exam).regId || registration(exam).registrationId) }
function rawRegistrationStatus(exam) {
  return String(registration(exam).status || exam.registrationStatus || exam.myStatus || '').toUpperCase()
}
function isRegistered(exam) {
  const status = rawRegistrationStatus(exam)
  return exam.registered === true || ['REGISTERED', 'PAID', 'CONFIRMED', 'APPROVED'].includes(status)
}
function now() { return Date.now() }
function timestamp(value) {
  if (!value) return null
  const result = new Date(value).getTime()
  return Number.isFinite(result) ? result : null
}
function withinWindow(exam) {
  const start = timestamp(exam.regStart || exam.registrationStart || exam.registerStart)
  const end = timestamp(exam.regEnd || exam.registrationEnd || exam.registerEnd)
  if (start != null && now() < start) return false
  if (end != null && now() > end) return false
  return true
}
function canRegister(exam) {
  if (pendingExamIds.value.includes(commandExamId(exam)) || isRegistered(exam) || !withinWindow(exam)) return false
  if (exam.canRegister === false || exam.eligible === false) return false
  const status = String(exam.status || '').toUpperCase()
  return status === 'OPEN'
}
function canCancel(exam) {
  if (pendingExamIds.value.includes(commandExamId(exam)) || !isRegistered(exam) || !withinWindow(exam) || exam.status !== 'OPEN') return false
  if (exam.canCancel === false) return false
  return !['PAID', 'CONFIRMED', 'APPROVED'].includes(rawRegistrationStatus(exam))
}
function registrationText(exam) {
  const status = rawRegistrationStatus(exam)
  const map = { REGISTERED: '已报名', PAID: '已缴费', CONFIRMED: '资格已确认', APPROVED: '资格已确认', CANCELLED: '已取消', REJECTED: '未通过' }
  if (map[status]) return map[status]
  if (canRegister(exam)) return '可报名'
  if (!withinWindow(exam)) return '窗口未开放'
  return '暂不可报名'
}
function blockReason(exam) {
  if (isRegistered(exam)) return ''
  if (exam.blockReason || exam.ineligibleReason) return exam.blockReason || exam.ineligibleReason
  if (!withinWindow(exam)) return '当前不在报名窗口内'
  if (exam.eligible === false) return '当前账号不符合本考试报名资格'
  return ''
}
function actionHint(exam) {
  if (isRegistered(exam)) return canCancel(exam) ? '报名窗口内可取消；取消后须重新校验资格。' : '当前报名已锁定，不能由学生端取消。'
  return canRegister(exam) ? '提交前请核对考试名称、等级和费用。' : blockReason(exam) || '请等待学校开放报名。'
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '待定' }
function feeText(value) {
  if (value == null || value === '') return '以学校通知为准'
  const amount = Number(value)
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : '以学校通知为准'
}
function startActing(id) {
  const token = ++actingToken
  actingIdentity = studentAcademicIdentity(session)
  actingId.value = String(id)
  return token
}
function finishActing(token, identity) {
  if (token === actingToken && identity === studentAcademicIdentity(session)) { actingId.value = ''; actingIdentity = '' }
}
function keepPendingAfterDeleteFailure(current) {
  receiptTone.value = 'waiting'
  receipt.value = academicReceipt({ title: '原等级考试办理结果待确认', object: current?.examName || current?.name || '原等级考试', status: '已读取正式记录，但本地待确认引用未能安全清除', next: '请只查询本人正式报名；确认本地引用已安全清除前，不会再次报名或取消。' })
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => ['REGISTER_LEVEL_EXAM', 'CANCEL_LEVEL_EXAM'].includes(item.action))
  pendingExamIds.value = [...new Set([...pending.map((item) => item.objectId), ...blockedExamIds.value])]
  for (const reference of pending) {
    const current = exams.value.find((item) => commandExamId(item) === reference.objectId)
    const status = current ? rawRegistrationStatus(current) : ''
    const exact = reference.ackId && current && registrationId(current) === reference.ackId
    const matched = reference.action === 'CANCEL_LEVEL_EXAM'
      ? exact && status === 'CANCELLED'
      : exact && ['REGISTERED', 'PAID', 'CONFIRMED', 'APPROVED', 'SCORED'].includes(status)
    if (matched) {
      if (guard.completePersistentCommand(reference)) {
        blockedExamIds.value = blockedExamIds.value.filter((value) => value !== reference.objectId)
        receiptTone.value = 'success'
        receipt.value = academicReceipt({ title: reference.action === 'CANCEL_LEVEL_EXAM' ? '原等级考试报名取消已确认' : '原等级考试报名已确认', object: current.examName || current.name || '原等级考试', status: registrationText(current), operatedAt: registration(current).updatedAt || registration(current).registeredAt, next: '报名、缴费、成绩和证书分别记录，请继续以本人正式记录为准。' })
        if (!selectedExamId.value || selectedExamId.value === reference.objectId) { selectedExamId.value = ''; confirmed.value = false }
        markStudentAcademicFormClean()
      } else {
        blockedExamIds.value = [...new Set([...blockedExamIds.value, reference.objectId])]
        keepPendingAfterDeleteFailure(current)
      }
    } else {
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '原等级考试办理结果待确认', object: current?.examName || current?.name || '原等级考试', status: reference.ackId ? '尚未读取到原回执对应的本人报名' : '原提交未取得服务端报名编号', next: '本页只会刷新本人正式报名，不会自动再次报名或取消；报名不代表缴费或取得证书。' })
    }
  }
  pendingExamIds.value = [...new Set([...guard.pendingCommands().filter((item) => ['REGISTER_LEVEL_EXAM', 'CANCEL_LEVEL_EXAM'].includes(item.action)).map((item) => item.objectId), ...blockedExamIds.value])]
}
async function load() {
  const identity = studentAcademicIdentity(session)
  if ((pageIdentity && pageIdentity !== identity) || (actingId.value && actingIdentity !== identity)) {
    actingToken += 1
    actingId.value = ''; actingIdentity = ''
    data.value = {}; pendingExamIds.value = []; blockedExamIds.value = []
    receipt.value = null; selectedExamId.value = ''; confirmed.value = false
  }
  pageIdentity = identity
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicLevelExam())
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '等级考试数据读取失败，请稍后重试')
    loading.value = false
    return false
  }
  data.value = read.value || {}
  reconcilePersistentCommands()
  loading.value = false
  return true
}
async function register(exam) {
  const id = commandExamId(exam)
  if (!id || actingId.value || !canRegister(exam)) return
  const command = guard.beginCommand({ examId: id, object: exam.examName || exam.name || '该等级考试' })
  const accepted = await systemConfirm({ title:'确认等级考试报名', message:`确认报名“${exam.examName || exam.name || '该等级考试'}”？`, confirmText:'确认报名' })
  if (!accepted || !guard.isCurrentCommand(command) || actingId.value) return
  const persistent = guard.preparePersistentCommand({ action: 'REGISTER_LEVEL_EXAM', objectId: command.examId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '等级考试报名未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  pendingExamIds.value = [...new Set([...pendingExamIds.value, command.examId])]
  const token = startActing(command.examId)
  try {
    const result = await portalApi.academicLevelRegister(id)
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = result?.examId == null || String(result.examId) === command.examId ? guard.rememberPersistentAck(persistent, result?.regId || result?.registrationId) : null
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '等级考试报名结果待确认', object: command.object, status: acknowledged ? '正在读取本人正式报名' : '服务端未返回可核对的报名编号', next: '确认前不要重复报名；报名不代表缴费。' })
    await load()
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    await handleActionError(e, command, persistent, '报名')
  } finally {
    finishActing(token, command.identity)
  }
}
async function cancel(exam) {
  const id = commandExamId(exam)
  if (!id || actingId.value || !canCancel(exam)) return
  const command = guard.beginCommand({ examId: id, object: exam.examName || exam.name || '该等级考试' })
  const accepted = await systemConfirm({ title:'确认取消报名', message:`确认取消“${exam.examName || exam.name || '该等级考试'}”报名？`, confirmText:'确认取消', type:'danger' })
  if (!accepted || !guard.isCurrentCommand(command) || actingId.value) return
  const persistent = guard.preparePersistentCommand({ action: 'CANCEL_LEVEL_EXAM', objectId: command.examId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '取消报名未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  pendingExamIds.value = [...new Set([...pendingExamIds.value, command.examId])]
  const token = startActing(command.examId)
  try {
    const result = await portalApi.academicLevelCancel(id)
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = result?.examId == null || String(result.examId) === command.examId ? guard.rememberPersistentAck(persistent, result?.regId || result?.registrationId) : null
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '取消报名结果待确认', object: command.object, status: acknowledged ? '正在读取本人正式报名' : '服务端未返回可核对的报名编号', next: '确认前不要重复取消。' })
    await load()
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    await handleActionError(e, command, persistent, '取消')
  } finally {
    finishActing(token, command.identity)
  }
}
function personalResult(exam) {
  const record = registration(exam)
  const fee = ({ PAID: '已缴费', UNPAID: '未缴费', EXEMPT: '免缴费' })[record.feeStatus] || '费用状态待确认'
  const result = ({ PASS: '合格', FAIL: '不合格', PENDING: '结果待发布' })[record.result] || '结果待发布'
  return [fee, result, record.score == null ? '' : `成绩 ${record.score}`, record.certNo ? `证书编号 ${record.certNo}` : ''].filter(Boolean).join(' · ')
}
async function handleActionError(e, command, persistent, action) {
  const kind = studentAcademicWriteErrorKind(e)
  const released = kind !== 'network' && guard.completePersistentCommand(persistent)
  if (kind !== 'network' && !released) {
    blockedExamIds.value = [...new Set([...blockedExamIds.value, command.examId])]
    keepPendingAfterDeleteFailure(exams.value.find((item) => commandExamId(item) === command.examId))
    return
  }
  if (released) {
    blockedExamIds.value = blockedExamIds.value.filter((value) => value !== command.examId)
    pendingExamIds.value = pendingExamIds.value.filter((value) => value !== command.examId)
  }
  if (kind === 'network' || kind === 'conflict') { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: kind === 'network' ? `${action}结果待确认` : '报名事实已变化', object: command.object, status: kind === 'network' ? '待服务器记录确认' : '本次办理未确认完成', next: academicErrorMessage(e, '请重新核对。') }); await load() }
  else ui.notify(academicErrorMessage(e, `${action}失败`))
}

function clearSensitive(e) {
  guard.invalidate()
  data.value = {}
  pendingExamIds.value = []; blockedExamIds.value = []
  receipt.value = null; selectedExamId.value = ''; confirmed.value = false
  actingId.value = ''; loading.value = false
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.definition{margin:14px 0}.form-notice{margin-top:14px}.field input.check{width:auto;accent-color:var(--pri)}</style>
