<template>
  <div data-academic-page class="sp-page academic-prototype exam-page">
    <AcademicPrototypeHeader :title="tab === 'apply' ? '缓考申请' : '考试与缓考'" group="成绩与考试" :object="tab === 'apply'" description="查看本人正式考试安排，跟踪缓考申请。" :loading="loading || !!actingKey" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人考试与缓考数据…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="tab === 'apply'">
        <AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>{{ selectedOption?.courseName || '选择本人考试' }} · 本人缓考申请</h2></header><form class="card-body" @submit.prevent="selectedOption && applyDefer(selectedOption)">
          <div class="form-grid">
            <label class="field"><span class="req">考试课程</span><select v-model="selectedOptionId"><option value="">请选择可办理考试</option><option v-for="option in deferOptions" :key="deferOptionKey(option)" :value="deferOptionKey(option)">{{ option.courseName }} · {{ dateText(option.examDate) }} {{ timeText(option) }}</option></select></label>
            <template v-if="selectedOption"><label class="field"><span class="req">事由类型</span><select v-model="drafts[selectedOptionId].reasonType"><option value="ILLNESS">疾病</option><option value="OFFICIAL">公务或学校安排</option><option value="FAMILY">家庭重大事项</option><option value="OTHER">其他</option></select></label><label class="field full"><span class="req">缓考说明</span><textarea v-model.trim="drafts[selectedOptionId].reason" maxlength="300" placeholder="说明无法按时参加考试的原因（至少 5 字）" /></label></template>
          </div><div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>提交后进入学校审核，未获批准前仍应按原考试安排准备。</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="tab = 'schedule'">返回考试安排</button><button class="btn primary" :disabled="!!actingKey || !selectedOption || !canApply(selectedOption)">{{ actingKey ? '提交中…' : '提交缓考申请' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>本页面只显示本人正式考试安排；缓考申请不会自动修改考试时间。</span></div>
        <StateBlock v-if="!exams.length" type="empty" text="暂无已发布的本人考试安排" />
        <div class="grid-equal"><section v-for="exam in exams" :key="examKey(exam)" class="card"><header class="card-head"><h2>{{ exam.courseName || '课程名称待补充' }}</h2></header><div class="card-body">
          <div class="row between"><span class="tag" :class="isPast(exam) ? 'gray' : 'green'">{{ isPast(exam) ? '已结束' : '已发布' }}</span><b>{{ dateText(exam.examDate || exam.startAt) }}</b></div>
          <dl class="definition"><dt>考试时间</dt><dd>{{ timeText(exam) }}</dd><dt>考试地点</dt><dd>{{ exam.roomName || exam.classroom || '考场待定' }}</dd><dt>本人座位</dt><dd>{{ exam.seatNo || '待定' }}</dd><dt>考试身份</dt><dd>本人正式考试安排</dd></dl>
          <footer class="form-foot"><button class="btn small" :disabled="!!actingKey" @click="printTicket(exam)">准考证 / 查询件</button><button v-if="optionForExam(exam)" class="btn primary small" @click="selectedOptionId = deferOptionKey(optionForExam(exam)); tab = 'apply'">申请缓考</button><span v-else class="label">当前暂无可办理的缓考申请</span></footer>
        </div></section></div>
        <button v-if="deferOptions.some(option => !exams.some(exam => String(exam.examCourseId) === String(option.examCourseId)))" class="btn" @click="tab = 'apply'">查看其他可申请缓考的考试</button>
        <section class="card"><header class="card-head"><h2>我的缓考申请</h2></header><div class="card-body">
          <p v-if="!deferrals.length" class="muted">暂无缓考申请。</p>
          <article v-for="record in deferrals" :key="record.deferId || record.id" :class="{ 'is-target': String(record.deferId || record.id) === focusDeferId }">
            <div class="taskline"><div class="iconbox amber"><AcademicPrototypeIcon name="circle-info" /></div><div class="grow"><strong>{{ record.courseName || '本人考试' }} · 缓考申请</strong><small>{{ dateTime(record.createdAt || record.applyAt) }} → {{ deferStatusText(record.status) }}</small></div><span class="tag amber">{{ deferStatusText(record.status) }}</span></div>
            <dl class="definition"><dt>申请说明</dt><dd>{{ record.reason || '未提供' }}</dd><dt v-if="record.reviewNote || record.rejectReason || record.returnReason">处理意见</dt><dd v-if="record.reviewNote || record.rejectReason || record.returnReason">{{ record.reviewNote || record.rejectReason || record.returnReason }}</dd></dl>
            <button v-if="record.status === 'RETURNED'" class="btn small" :disabled="!!actingKey" @click="resubmit(record)">确认补充完成并重提</button>
          </article><p class="label">以受理节点返回为准，不把“学院通过”显示成全流程批准。</p>
        </div></section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'

import { portalApi } from '../../services/portalApi'
import { createInAppPrintFrame } from '../../services/printInApp'
import { systemConfirm, systemPrompt } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'exam-defer')
const route = useRoute()
const focusDeferId = computed(() => String(route.query.deferId || ''))
const loading = ref(true)
const error = ref('')
const actingKey = ref('')
const tab = ref(['schedule', 'apply', 'records'].includes(String(route.query.tab)) ? String(route.query.tab) : 'schedule')
const exams = ref([])
const deferOptions = ref([])
const deferrals = ref([])
const receipt = ref(null)
const receiptTone = ref('success')
const drafts = reactive({})
const selectedOptionId = ref('')
const uncertainKeys = ref([])
const selectedOption = computed(() => deferOptions.value.find(option => deferOptionKey(option) === selectedOptionId.value))
function optionForExam(exam) { return deferOptions.value.find(option => String(option.examCourseId) === String(exam.examCourseId)) }

const returnedDeferrals = computed(() => deferrals.value.filter((record) => String(record.status || '').toUpperCase() === 'RETURNED'))

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records || data.exams || data.options)) || []
}
function examKey(exam) { return String(exam.examRoomStudentId || exam.examCourseId || exam.examId || `${exam.courseCode}:${exam.examDate || exam.startAt}`) }
function deferOptionKey(option) { return String(option.examCourseId || option.id || examKey(option)) }
function dateText(value) { return String(value || '').slice(0, 10) || '日期待定' }
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
function timeText(exam) {
  const start = String(exam.startTime || '').slice(0, 5)
  const end = String(exam.endTime || '').slice(0, 5)
  if (start && end) return `${start}-${end}`
  if (start) return start
  const startAt = String(exam.startAt || '')
  const endAt = String(exam.endAt || '')
  const startPart = startAt.includes('T') ? startAt.slice(11, 16) : ''
  const endPart = endAt.includes('T') ? endAt.slice(11, 16) : ''
  return startPart && endPart ? `${startPart}-${endPart}` : startPart || '时间待定'
}
function examTimestamp(exam) {
  const raw = exam.endAt || exam.startAt || (exam.examDate && `${exam.examDate}T${exam.endTime || exam.startTime || '23:59'}`)
  const value = raw ? new Date(raw).getTime() : NaN
  return Number.isFinite(value) ? value : null
}
function isPast(exam) {
  const value = examTimestamp(exam)
  return value != null && value < Date.now()
}
function deferStatusText(value) {
  const map = { SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核中', TEACHER_CONFIRM: '任课教师确认中', ACADEMIC_REVIEW: '教务审核中', APPROVED: '已批准', REJECTED: '未批准', RETURNED: '退回待补充', CANCELLED: '已撤销' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function ensureDraft(option) {
  const key = deferOptionKey(option)
  if (!drafts[key]) drafts[key] = { reasonType: 'ILLNESS', reason: '' }
}
function canApply(option) {
  const draft = drafts[deferOptionKey(option)]
  return !uncertainKeys.value.includes(`apply:${deferOptionKey(option)}`) && !!option?.examCourseId && !!draft?.reasonType && String(draft.reason || '').trim().length >= 5
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => ['APPLY_DEFER', 'RESUBMIT_DEFER'].includes(item.action))
  uncertainKeys.value = pending.map((item) => `${item.action === 'APPLY_DEFER' ? 'apply' : 'resubmit'}:${item.objectId}`)
  for (const reference of pending) {
    const applying = reference.action === 'APPLY_DEFER'
    const formal = reference.ackId ? deferrals.value.find((row) => String(row.deferId || row.id || '') === reference.ackId) : null
    const confirmed = applying
      ? formal && String(formal.examCourseId || '') === reference.objectId
      : formal && reference.ackId === reference.objectId && String(formal.status || '').toUpperCase() !== 'RETURNED'
    if (confirmed && guard.completePersistentCommand(reference)) {
      receiptTone.value = 'success'
      receipt.value = academicReceipt({ title: `原缓考申请${applying ? '' : '重新'}提交已通过正式记录确认`, object: formal.courseName || formal.examName || '原考试', status: deferStatusText(formal.status), operatedAt: formal.updatedAt || formal.createdAt || formal.submittedAt, next: '请继续在申请记录中跟踪学校受理结果。' })
    } else {
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '原缓考申请结果待确认', object: formal?.courseName || formal?.examName || '原考试', status: reference.ackId ? (confirmed ? '正式记录已读到，但本地待确认引用未能安全清理' : formal ? '原申请仍待重新提交确认' : '尚未读取到原回执对应的本人记录') : '原提交未取得服务端回执编号', next: '本页只会刷新本人正式记录，不会自动再次提交。' })
    }
  }
  uncertainKeys.value = guard.pendingCommands().filter((item) => ['APPLY_DEFER', 'RESUBMIT_DEFER'].includes(item.action)).map((item) => `${item.action === 'APPLY_DEFER' ? 'apply' : 'resubmit'}:${item.objectId}`)
}
async function load() {
  if (!actingKey.value) receipt.value = null
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => Promise.all([
      portalApi.academicExam(),
      portalApi.academicExamDeferOptions(),
      portalApi.academicExamDefer()
  ]))
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '考试与缓考数据读取失败，请稍后重试')
    loading.value = false
    return false
  }
  const [examResult, optionResult, recordResult] = read.value
  exams.value = rowsOf(examResult)
  deferOptions.value = rowsOf(optionResult)
  deferrals.value = rowsOf(recordResult)
  reconcilePersistentCommands()
  for (const option of deferOptions.value) ensureDraft(option)
  if (returnedDeferrals.value.length && tab.value === 'schedule') tab.value = 'records'
  loading.value = false
  return true
}
async function applyDefer(option) {
  const key = deferOptionKey(option)
  if (actingKey.value || !canApply(option)) return
  const draft = drafts[key]
  const command = guard.beginCommand({ key: `apply:${key}`, examCourseId: String(option.examCourseId), reasonType: draft.reasonType, reason: String(draft.reason || '').trim(), object: option.courseName || option.examName || '当前考试' })
  if (!await systemConfirm({ title:'确认缓考申请', message:`确认对“${command.object}”提交缓考申请？原考试安排在批准前仍然有效。`, confirmText:'提交缓考申请' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'APPLY_DEFER', objectId: command.examCourseId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '缓考申请未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  actingKey.value = command.key
  try {
    const result = await portalApi.academicExamDeferApply({
      examCourseId: command.examCourseId,
      reasonType: command.reasonType,
      reason: command.reason
    })
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.deferId || result?.id)
    uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '正在读取本人正式缓考申请', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    const formal = acknowledged?.ackId ? deferrals.value.find((row) => String(row.deferId || row.id) === acknowledged.ackId) : null
    const sameExam = formal && String(formal.examCourseId || '') === command.examCourseId
    if (sameExam && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'; receipt.value = academicReceipt({ title: '缓考申请已提交并核对', object: command.object, status: deferStatusText(formal.status), operatedAt: formal.createdAt || formal.submittedAt || result?.createdAt, next: '原考试安排仍然有效，请在申请记录中跟踪学校受理结果。' })
      uncertainKeys.value = uncertainKeys.value.filter(value => value !== command.key)
      drafts[key] = { reasonType: 'ILLNESS', reason: '' }; tab.value = 'records'
      markStudentAcademicFormClean()
    } else {
      uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '尚未读取到匹配的本人缓考申请', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    await handleActionError(e, command, '缓考申请', persistent)
  } finally {
    if (guard.isCurrentCommand(command)) actingKey.value = ''
  }
}
async function resubmit(record) {
  const id = record?.deferId || record?.id
  const commandKey = `resubmit:${String(id || '')}`
  if (!id || actingKey.value || uncertainKeys.value.includes(commandKey)) return
  const command = guard.beginCommand({ key: commandKey, deferId: String(id), object: record.courseName || record.examName || '当前考试' })
  if (!await systemConfirm({ title:'确认重新提交缓考', message:`确认已按处理意见补充“${command.object}”并重新提交？`, confirmText:'确认重新提交' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'RESUBMIT_DEFER', objectId: command.deferId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '缓考重新提交未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  actingKey.value = command.key
  try {
    const result = await portalApi.academicExamDeferResubmit(command.deferId)
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.deferId || result?.id)
    uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '重新提交结果待正式记录确认', object: command.object, status: '正在读取本人正式缓考申请', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    const formal = acknowledged?.ackId === command.deferId ? deferrals.value.find((row) => String(row.deferId || row.id) === command.deferId) : null
    if (formal && String(formal.status || '').toUpperCase() !== 'RETURNED' && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'; receipt.value = academicReceipt({ title: '缓考申请已重新提交并核对', object: command.object, status: deferStatusText(formal.status), operatedAt: formal.updatedAt || formal.submittedAt || result?.updatedAt, next: '请继续在申请记录中跟踪学校受理结果。' })
      uncertainKeys.value = uncertainKeys.value.filter(value => value !== command.key)
      markStudentAcademicFormClean()
    } else {
      uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '重新提交结果待正式记录确认', object: command.object, status: formal ? deferStatusText(formal.status) : '未读到本人缓考申请', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    await handleActionError(e, command, '重新提交', persistent)
  } finally {
    if (guard.isCurrentCommand(command)) actingKey.value = ''
  }
}
async function printTicket(exam) {
  if (actingKey.value || loading.value || error.value) return
  const reason = await systemPrompt({ title:'填写考试安排开具事由', message:'本次事由将写入审计记录。', defaultValue:'本人考试安排查询', minLength:5, confirmText:'确认开具' })
  if (reason == null) return
  if (reason.trim().length < 5) { ui.notify('开具事由不少于5个字'); return }
  const win = createInAppPrintFrame('本人考试查询件')
  win.document.body.textContent = '正在读取正式考试查询件…'
  actingKey.value = 'print:' + examKey(exam)
  try {
    const audit = await portalApi.academicExamTicketPrint({ bizId: examKey(exam), reason: reason.trim() })
    const document = audit?.document
    const items = rowsOf(document)
    if (!items.length) throw new Error('学校暂未返回可打印的本人正式考试安排')
    const doc = win.document
    doc.title = '本人考试查询件'; doc.body.textContent = ''
    const append = (parent, tag, value) => { const node = doc.createElement(tag); node.textContent = String(value ?? ''); parent.appendChild(node); return node }
    const style = doc.createElement('style')
    style.textContent = 'body{font-family:Microsoft YaHei,sans-serif;padding:28px;color:#203450}h1{text-align:center;font-size:22px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{border:1px solid #dce5f3;padding:10px;text-align:left}p{font-size:12px;color:#586d89}.watermark{position:fixed;top:42%;left:10%;transform:rotate(-25deg);color:rgba(32,52,80,.09);font-size:32px;pointer-events:none}'
    doc.head.appendChild(style)
    append(doc.body, 'h1', '本人考试查询件')
    append(doc.body, 'p', [document.realName, document.studentNo, '开具事由：' + reason.trim(), '留痕时间：' + (audit.loggedAt || '以学校记录为准')].filter(Boolean).join(' · '))
    if (audit.watermark) append(doc.body, 'div', audit.watermark).className = 'watermark'
    const table = append(doc.body, 'table', '')
    const header = append(table, 'tr', '')
    for (const title of ['考试课程','日期','时间','考场','座位','准考编号']) append(header, 'th', title)
    for (const item of items) { const row = append(table, 'tr', ''); for (const value of [item.courseName, dateText(item.examDate || item.startAt), timeText(item), item.classroom || item.roomName, item.seatNo, item.admissionNo]) append(row, 'td', value || '待公布') }
    append(doc.body, 'p', '考试信息来自学校本人正式安排。入场证件要求以学校通知为准。')
    win.focus(); win.print()
  } catch (e) {
    if (!win.closed) win.close()
    if (studentAcademicWriteErrorKind(e) === 'forbidden') clearSensitive(e)
    else ui.notify(academicErrorMessage(e, '考试查询件生成失败'))
  } finally { actingKey.value = '' }
}
async function handleActionError(e, command, action, persistent) {
  const kind = studentAcademicWriteErrorKind(e)
  if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
  if (kind === 'network' || kind === 'conflict') uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
  if (kind === 'network' || kind === 'conflict') { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: kind === 'network' ? `${action}结果待确认` : '考试事实已变化', object: command.object, status: '待服务器记录确认', next: academicErrorMessage(e, '请重新核对。') }); await load() }
  else ui.notify(academicErrorMessage(e, `${action}失败`))
}

function clearSensitive(e) {
  guard.invalidate()
  exams.value = []; deferOptions.value = []; deferrals.value = []; Object.keys(drafts).forEach((key) => delete drafts[key])
  receipt.value = null; selectedOptionId.value = ''
  loading.value = false; actingKey.value = ''
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.definition{margin:14px 0}.form-notice{margin-top:14px}.is-target{outline:2px solid var(--pri);outline-offset:4px;border-radius:8px}</style>
