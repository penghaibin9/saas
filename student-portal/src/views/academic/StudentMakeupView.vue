<template>
  <div data-academic-page class="sp-page academic-prototype makeup-page">
    <AcademicPrototypeHeader :title="tab === 'overview' ? '补考重修' : '重修或免修申请'" group="成绩与考试" :object="tab !== 'overview'" description="核对课程补救安排，重修与免修分别办理。" :loading="loading || !!actingKey" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人补考重修数据…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack"><AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="tab !== 'overview'"><AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>{{ activeOption?.courseName || '选择本人课程' }} · {{ tab === 'retake' ? '重修报名' : '免修申请' }}</h2></header><form class="card-body" @submit.prevent="activeOption && (tab === 'retake' ? applyRetake(activeOption) : applyExemption(activeOption))">
          <div class="form-grid"><label class="field"><span class="req">{{ tab === 'retake' ? '来源正式成绩' : '目标正式课程' }}</span><select v-model="activeOptionId"><option value="">请选择本人课程</option><option v-for="option in currentOptions" :key="tab === 'retake' ? retakeKey(option) : exemptionKey(option)" :value="tab === 'retake' ? retakeKey(option) : exemptionKey(option)">{{ option.courseName }} · {{ option.courseCode || '正式课程' }}</option></select></label>
            <label class="field"><span>申请类型</span><select v-model="tab" @change="activeOptionId = ''"><option value="retake">重修报名</option><option value="exemption">免修申请</option></select></label>
            <label v-if="activeOption" class="field full"><span class="req">申请说明</span><textarea v-if="tab === 'retake'" v-model.trim="retakeReasons[retakeKey(activeOption)]" maxlength="300" placeholder="请说明重修申请事由（至少 2 字）" /><textarea v-else v-model.trim="exemptionReasons[exemptionKey(activeOption)]" maxlength="300" placeholder="请说明免修申请事由（至少 2 字）" /></label></div>
          <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>{{ activeOption && optionBlockReason(activeOption, tab) || '重修与免修是不同申请；提交后由学校按各自规则审核，不直接生成正式成绩。' }}</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="tab = 'overview'">返回补考重修</button><button class="btn primary" :disabled="!!actingKey || !activeOption || !(tab === 'retake' ? canApplyRetake(activeOption) : canApplyExemption(activeOption))">{{ actingKey ? '提交中…' : tab === 'retake' ? '提交重修报名' : '提交免修申请' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <div class="notice amber"><AcademicPrototypeIcon name="circle-info" /><span>补考安排、重修报名、免修申请各自有状态；它们不会由学生直接创建正式成绩。</span></div>
        <section class="card"><header class="card-head"><h2>需要补救的课程</h2><span class="tag">正式成绩来源</span></header><div class="card-body"><StateBlock v-if="!retakeOptions.length" type="empty" text="暂无本人可申请重修的课程" />
          <article v-for="option in retakeOptions" :key="retakeKey(option)" class="course-block" :class="{ 'is-target': retakeKey(option) === focusOptionId }"><h2>{{ option.courseName }}</h2><p class="muted">{{ option.termCode || '学期待提供' }} · {{ scoreLabel(option) }} · {{ option.credit ?? '学分待确认' }} 学分</p><dl class="definition"><dt>补考安排</dt><dd>{{ option.examDate || option.arrangement || '学校尚未提供本课程补考时间' }}</dd><dt>重修申请</dt><dd>{{ optionBlockReason(option, 'retake') || '当前可发起申请，是否受理以学校规则为准' }}</dd><dt>来源身份</dt><dd>{{ option.courseCode || '本人正式成绩' }} · {{ retakeKey(option) || '身份待补全' }}</dd></dl><footer class="form-foot"><RouterLink class="btn" to="/academic/grades">查看原成绩</RouterLink><button class="btn primary" :disabled="!!optionBlockReason(option, 'retake')" @click="activeOptionId = retakeKey(option); tab = 'retake'">申请重修</button></footer></article>
        </div></section>
        <section v-if="exemptionOptions.length" class="card"><header class="card-head"><h2>可申请免修的课程</h2></header><div class="card-body"><div v-for="option in exemptionOptions" :key="exemptionKey(option)" class="taskline"><div class="grow"><strong>{{ option.courseName }}</strong><small>{{ optionBlockReason(option, 'exemption') || option.courseCode }}</small></div><button class="btn small" :disabled="!!optionBlockReason(option, 'exemption')" @click="activeOptionId = exemptionKey(option); tab = 'exemption'">申请免修</button></div></div></section>
        <section class="card"><header class="card-head"><h2>本人办理记录</h2></header><div class="card-body"><p v-if="!overviewRows.length" class="muted">暂无本人补考、重修或免修办理记录。</p><div v-for="row in overviewRows" :key="recordKey(row)" class="taskline"><div class="grow"><strong>{{ row.courseName || '本人课程' }} · {{ row.recordType || '课程补救' }}</strong><small>{{ row.reason || row.remark || '正式结果在成绩页核对' }}</small></div><span class="tag" :class="recordStatusTone(row) === 'success' ? 'green' : recordStatusTone(row) === 'danger' ? 'red' : 'amber'">{{ recordStatusText(row) }}</span></div></div></section>
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
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'makeup')
const route = useRoute()
const focusOptionId = computed(() => String(route.query.optionId || ''))
const loading = ref(true)
const error = ref('')
const actingKey = ref('')
const tab = ref(['overview', 'retake', 'exemption'].includes(String(route.query.tab)) ? String(route.query.tab) : 'overview')
const overview = ref({})
const options = ref({ retakeOptions: [], exemptionOptions: [] })
const receipt = ref(null)
const receiptTone = ref('success')
const retakeReasons = reactive({})
const exemptionReasons = reactive({})
const activeOptionId = ref(String(route.query.optionId || ''))
const uncertainKeys = ref([])
const currentOptions = computed(() => tab.value === 'retake' ? retakeOptions.value : exemptionOptions.value)
const activeOption = computed(() => currentOptions.value.find(option => (tab.value === 'retake' ? retakeKey(option) : exemptionKey(option)) === activeOptionId.value))

const overviewRows = computed(() => rowsOf(overview.value))
const retakeOptions = computed(() => Array.isArray(options.value.retakeOptions) ? options.value.retakeOptions : [])
const exemptionOptions = computed(() => Array.isArray(options.value.exemptionOptions) ? options.value.exemptionOptions : [])

function rowsOf(data) {
  if (Array.isArray(data)) return data
  if (data?.retakes || data?.exemptions) return [...(data.retakes || []).map((row) => ({ ...row, recordType: '重修' })), ...(data.exemptions || []).map((row) => ({ ...row, recordType: '免修' }))]
  return (data && (data.items || data.list || data.records)) || []
}
function recordKey(row) {
  return String(row.recordType || '') + ':' + String(row.id || row.makeupId || row.retakeId || row.exemptionId || `${row.courseCode || row.courseName}:${row.termCode || ''}`)
}
function retakeKey(option) {
  return String(option.gradeId || option.acadGradeId || '')
}
function exemptionKey(option) {
  return String(option.courseId || '')
}
function formalApplication(type, result) {
  const id = type === 'retake' ? (result?.retakeId || result?.applyId || result?.id) : (result?.exemptionId || result?.applyId || result?.id)
  if (!id) return null
  return overviewRows.value.find((row) => row.recordType === (type === 'retake' ? '重修' : '免修') && String(row.retakeId || row.exemptionId || row.applyId || row.id) === String(id)) || null
}
function scoreLabel(option) {
  const value = option.score ?? option.originalScore ?? option.totalScore
  return value == null ? '未通过课程' : `原成绩 ${value}`
}
function courseStatusText(value) {
  const map = { PENDING: '待处理', ELIGIBLE: '符合条件', SCHEDULED: '已安排', COMPLETED: '已完成', PASSED: '已通过', FAILED: '未通过' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function applicationStatusText(value) {
  const map = { PENDING: '审核中', SUBMITTED: '已提交', APPROVED: '已通过', REJECTED: '未通过', RETURNED: '已退回', CANCELLED: '已取消' }
  return map[String(value || '').toUpperCase()] || value || '暂无申请'
}
function recordStatusText(row) {
  return applicationStatusText(row.applyStatus) !== '暂无申请'
    ? applicationStatusText(row.applyStatus)
    : courseStatusText(row.status)
}
function recordStatusTone(row) {
  const value = String(row.applyStatus || row.status || '').toUpperCase()
  if (['APPROVED', 'COMPLETED', 'PASSED'].includes(value)) return 'success'
  if (['REJECTED', 'FAILED', 'CANCELLED'].includes(value)) return 'danger'
  return 'warn'
}
function canApplyRetake(option) {
  return !uncertainKeys.value.includes(`retake:${retakeKey(option)}`) && !optionBlockReason(option, 'retake') && String(retakeReasons[retakeKey(option)] || '').trim().length >= 2
}
function canApplyExemption(option) {
  return !uncertainKeys.value.includes(`exemption:${exemptionKey(option)}`) && !optionBlockReason(option, 'exemption') && String(exemptionReasons[exemptionKey(option)] || '').trim().length >= 2
}
function optionBlockReason(option, type) {
  if (option.identityDebt === true || option.identityReady === false || !(type === 'retake' ? retakeKey(option) : exemptionKey(option))) return '课程身份资料尚未完整，暂不能在线申请。请联系教务老师补全后刷新。'
  return ''
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => ['APPLY_RETAKE', 'APPLY_EXEMPTION'].includes(item.action))
  uncertainKeys.value = pending.map((item) => `${item.action === 'APPLY_RETAKE' ? 'retake' : 'exemption'}:${item.objectId}`)
  for (const reference of pending) {
    const type = reference.action === 'APPLY_RETAKE' ? 'retake' : 'exemption'
    const formal = reference.ackId ? overviewRows.value.find((row) => row.recordType === (type === 'retake' ? '重修' : '免修') && String(row.retakeId || row.exemptionId || row.applyId || row.id || '') === reference.ackId) : null
    const formalSource = type === 'retake' ? String(formal?.originGradeId || formal?.gradeId || '') : String(formal?.course?.id || formal?.courseId || '')
    if (formal && formalSource === reference.objectId && guard.completePersistentCommand(reference)) {
      receiptTone.value = 'success'
      receipt.value = academicReceipt({ title: `原${type === 'retake' ? '重修报名' : '免修申请'}已通过正式记录确认`, object: formal.courseName || '原课程', status: recordStatusText(formal), operatedAt: formal.createdAt || formal.submittedAt, next: '请继续核对学校后续处理。' })
    } else {
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: `原${type === 'retake' ? '重修报名' : '免修申请'}结果待确认`, object: formal?.courseName || '原课程', status: !reference.ackId ? '原提交未取得服务端回执编号' : formal && formalSource === reference.objectId ? '正式记录已读到，但本地待确认引用未能安全清理' : formal ? '正式记录缺少原课程对象，暂不能完成归因' : '尚未读取到原回执对应的本人记录', next: '本页只会刷新本人正式记录，不会自动再次提交。' })
    }
  }
  uncertainKeys.value = guard.pendingCommands().filter((item) => ['APPLY_RETAKE', 'APPLY_EXEMPTION'].includes(item.action)).map((item) => `${item.action === 'APPLY_RETAKE' ? 'retake' : 'exemption'}:${item.objectId}`)
}
async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => Promise.all([
      portalApi.academicMakeup(),
      portalApi.academicMakeupOptions()
  ]))
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '补考重修数据读取失败，请稍后重试')
    loading.value = false
    return false
  }
  const [overviewResult, optionsResult] = read.value
  overview.value = overviewResult || {}
  options.value = optionsResult || { retakeOptions: [], exemptionOptions: [] }
  reconcilePersistentCommands()
  for (const option of retakeOptions.value) {
    const key = retakeKey(option)
    if (retakeReasons[key] == null) retakeReasons[key] = ''
  }
  for (const option of exemptionOptions.value) {
    const key = exemptionKey(option)
    if (exemptionReasons[key] == null) exemptionReasons[key] = ''
  }
  loading.value = false
  return true
}
async function applyRetake(option) {
  const key = retakeKey(option)
  if (actingKey.value || !canApplyRetake(option)) return
  const commandKey = `retake:${key}`
  const command = guard.beginCommand({ key: commandKey, gradeId: String(option.gradeId || option.acadGradeId), reason: String(retakeReasons[key] || '').trim(), object: option.courseName || '当前课程' })
  if (!await systemConfirm({ title:'确认重修报名', message:`确认对“${command.object}”提交重修报名？`, confirmText:'确认报名' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'APPLY_RETAKE', objectId: command.gradeId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '重修报名未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  actingKey.value = commandKey
  try {
    const result = await portalApi.academicRetakeApply({
      gradeId: command.gradeId,
      reason: command.reason
    })
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.retakeId || result?.applyId || result?.id)
    uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '正在读取本人正式重修申请', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    const formal = acknowledged?.ackId ? formalApplication('retake', { retakeId: acknowledged.ackId }) : null
    const sameOrigin = formal && String(formal.originGradeId || formal.gradeId || '') === command.gradeId
    if (sameOrigin && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'; receipt.value = academicReceipt({ title: '重修报名已提交并核对', object: command.object, status: recordStatusText(formal), operatedAt: formal.createdAt || formal.submittedAt || result?.createdAt, next: '请继续核对学校安排；提交申请不代表已取得新教学班名额。' }); retakeReasons[key] = ''
      uncertainKeys.value = uncertainKeys.value.filter(value => value !== command.key)
      tab.value = 'overview'; activeOptionId.value = ''
      markStudentAcademicFormClean()
    } else {
      uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '尚未读取到匹配的本人重修申请', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    await handleActionError(e, command, '重修报名', persistent)
  } finally {
    if (guard.isCurrentCommand(command)) actingKey.value = ''
  }
}
async function applyExemption(option) {
  const key = exemptionKey(option)
  if (actingKey.value || !canApplyExemption(option)) return
  const commandKey = `exemption:${key}`
  const command = guard.beginCommand({ key: commandKey, courseId: String(option.courseId), courseName: option.courseName || '当前课程', reason: String(exemptionReasons[key] || '').trim() })
  if (!await systemConfirm({ title:'确认免修申请', message:`确认对“${command.courseName}”提交免修申请？`, confirmText:'提交免修申请' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'APPLY_EXEMPTION', objectId: command.courseId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '免修申请未发送', object: command.courseName, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  actingKey.value = commandKey
  try {
    const result = await portalApi.academicExemptionApply({
      courseId: command.courseId,
      courseName: command.courseName,
      reason: command.reason
    })
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.exemptionId || result?.applyId || result?.id)
    uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.courseName, status: '正在读取本人正式免修申请', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    const formal = acknowledged?.ackId ? formalApplication('exemption', { exemptionId: acknowledged.ackId }) : null
    const sameCourse = formal && String(formal.course?.id || formal.courseId || '') === command.courseId
    if (sameCourse && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'; receipt.value = academicReceipt({ title: '免修申请已提交并核对', object: command.courseName, status: recordStatusText(formal), operatedAt: formal.createdAt || formal.submittedAt || result?.createdAt, next: '原课程要求保持不变，请等待学校审核正式结果。' }); exemptionReasons[key] = ''
      uncertainKeys.value = uncertainKeys.value.filter(value => value !== command.key)
      tab.value = 'overview'; activeOptionId.value = ''
      markStudentAcademicFormClean()
    } else {
      uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.courseName, status: '尚未读取到匹配的本人免修申请', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    await handleActionError(e, command, '免修申请', persistent)
  } finally {
    if (guard.isCurrentCommand(command)) actingKey.value = ''
  }
}
async function handleActionError(e, command, action, persistent) {
  const kind = studentAcademicWriteErrorKind(e)
  if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
  if (kind === 'network' || kind === 'conflict') uncertainKeys.value = [...new Set([...uncertainKeys.value, command.key])]
  if (kind === 'network' || kind === 'conflict') { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: kind === 'network' ? `${action}结果待确认` : '课程事实已变化', object: command.object || command.courseName, status: '待服务器记录确认', next: academicErrorMessage(e, '请重新核对。') }); await load() }
  else ui.notify(academicErrorMessage(e, `${action}失败`))
}

function clearSensitive(e) {
  guard.invalidate()
  overview.value = {}; options.value = { retakeOptions: [], exemptionOptions: [] }; Object.keys(retakeReasons).forEach((key) => delete retakeReasons[key]); Object.keys(exemptionReasons).forEach((key) => delete exemptionReasons[key])
  receipt.value = null; activeOptionId.value = ''; tab.value = 'overview'
  loading.value = false; actingKey.value = ''
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.definition{margin:14px 0}.form-notice{margin-top:14px}.course-block + .course-block{border-top:1px solid var(--line);margin-top:18px;padding-top:18px}.is-target{outline:2px solid var(--pri);outline-offset:4px}</style>
