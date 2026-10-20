<template>
  <div data-academic-page class="sp-page academic-prototype registration-page">
    <AcademicPrototypeHeader :title="deferBatch ? '暂缓注册申请' : '学期注册'" group="注册与安排" :object="!!deferBatch" description="核对本人注册资格，完成本学期注册。" :loading="loading || !!actingId" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人注册批次…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="registrationReceipt" :tone="actionReceipt?.result === '本学期注册已完成' ? 'success' : 'waiting'" />
      <template v-if="deferBatch">
        <AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>{{ deferBatch.batchName }} · 本人申请</h2></header><form class="card-body" @submit.prevent="submitDefer(deferBatch)">
          <div class="form-grid"><label class="field"><span>申请期限</span><AppDatePicker v-model="deferUntil[deferBatch.batchId]" class="input" aria-label="申请期限" /></label><label class="field full"><span class="req">暂缓事由</span><textarea v-model.trim="deferReasons[deferBatch.batchId]" maxlength="300" placeholder="说明暂时无法完成注册的原因（至少 2 字）" /></label></div>
          <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>提交后进入学校受理；申请日期不是自动批准的日期。</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="deferBatchId = ''">返回注册</button><button class="btn primary" :disabled="!deferBatch.canDefer || !!actingId || !canDefer(deferBatch)">{{ actingId ? '提交中…' : '提交暂缓申请' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <AcademicPrototypeSteps :labels="['学校建批次', '本人资格核验', '本人确认', '学校登记结果']" :active="registrationStep" />
        <StateBlock v-if="!batches.length" type="empty" :text="data.note || '暂无开放中的注册批次'" />
        <div v-for="batch in batches" :key="batch.batchId" class="grid2" :class="{ 'is-target': String(batch.batchId) === focusBatchId }">
          <section class="card"><header class="card-head"><h2>{{ batch.batchName || '学期注册' }}</h2></header><div class="card-body">
            <div class="row between"><span class="tag" :class="batch.registrationStatus === 'REGISTERED' ? 'green' : 'amber'">{{ registrationStatusText(batch.registrationStatus) }}</span><small>开放至 {{ dateText(batch.windowEnd) }}</small></div>
            <dl class="definition"><dt>学籍身份</dt><dd>{{ studentStatusText(data.studentStatus) }} · {{ data.className || data.studentNo || '本人' }}</dd><dt>当前批次</dt><dd>{{ batch.batchName || '学校已建立的注册批次' }}</dd><dt>资格核验</dt><dd><span class="tag" :class="batch.eligibilityStatus === 'ELIGIBLE' ? 'green' : 'amber'">{{ eligibilityText(batch.eligibilityStatus) }}</span></dd><dt>提交后</dt><dd>以服务器返回的登记状态为准</dd></dl>
            <div v-if="batch.blockReason" class="notice amber">{{ batch.blockReason }}</div>
            <div class="form-foot"><button class="btn" :disabled="!batch.canDefer || !!actingId" @click="deferBatchId = String(batch.batchId)">申请暂缓</button><button class="btn primary" :disabled="batch.canRegister !== true || !!actingId || !!uncertainRegistrations[String(batch.batchId)]" @click="openRegisterConfirm(batch)">确认本人注册</button></div>
          </div></section>
          <section class="card"><header class="card-head"><h2>我发起的申请</h2></header><div class="card-body"><p class="muted">{{ batch.deferral ? deferralText(batch.deferral) : '暂无本批次暂缓申请。' }}</p><div class="divider"></div><h3>无法按期完成？</h3><p class="muted">提交暂缓事由和申请期限，由学校受理；不等于自动注册成功。</p><div class="form-notice"><RouterLink class="btn link" to="/academic/status">查看当前学籍</RouterLink></div></div></section>
        </div>
      </template>
    </div>
    <div v-if="pendingRegistration" class="confirm-backdrop" @click.self="closeRegisterConfirm">
      <section class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="registration-confirm-title">
        <div class="confirm-dialog__eyebrow">注册确认</div>
        <h2 id="registration-confirm-title">确认完成本学期注册？</h2>
        <p>提交后将以本人身份记录注册结果，并立即刷新当前批次状态。</p>
        <dl>
          <div><dt>注册批次</dt><dd>{{ pendingRegistration.batchName || '当前批次' }}</dd></div>
          <div><dt>批次编号</dt><dd>{{ pendingRegistration.batchId }}</dd></div>
          <div><dt>注册资格</dt><dd>{{ eligibilityText(pendingRegistration.eligibilityStatus) }}</dd></div>
        </dl>
        <footer>
          <button class="btn" type="button" :disabled="!!actingId" @click="closeRegisterConfirm">暂不注册</button>
          <button class="btn primary" type="button" :disabled="!!actingId" @click="register(pendingRegistration)">
            {{ actingId ? '注册中…' : '确认并提交注册' }}
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { academicErrorKind, academicErrorMessage, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AppDatePicker from '../../components/AppDatePicker.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'
import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { localizeVisibleEnumText } from '../../services/visibleEnumLocalization'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'registration')
const route = useRoute()
const focusBatchId = computed(() => String(route.query.batchId || ''))
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const data = ref({ batches: [] })
const deferReasons = reactive({})
const deferUntil = reactive({})
const deferBatchId = ref('')
const deferBatch = computed(() => batches.value.find(batch => String(batch.batchId) === deferBatchId.value))
const registrationReceipt = computed(() => actionReceipt.value ? { title: actionReceipt.value.result, object: actionReceipt.value.batchName, status: actionReceipt.value.result, operatedAt: actionReceipt.value.operatedAt || '以学校办理记录为准', next: actionReceipt.value.next, relatedTo: '/academic/schedule', relatedLabel: '查看本学期课表' } : null)
const pendingRegistration = ref(null)
const actionReceipt = ref(null)
const uncertainDeferralKeys = ref([])
const uncertainRegistrations = ref({})

const batches = computed(() => Array.isArray(data.value.batches) ? data.value.batches : [])
const registrationStep = computed(() => !batches.value.length ? 0 : batches.value.every(batch => batch.registrationStatus === 'REGISTERED') ? 3 : batches.value.every(batch => batch.eligibilityStatus === 'ELIGIBLE') ? 2 : 1)

function dateText(value) {
  return String(value || '').slice(0, 10) || '待定'
}
function studentStatusText(status) {
  return localizeVisibleEnumText(status || '待确认')
}
function registrationStatusText(status) {
  const map = {
    PENDING: '待注册', PENDING_REGISTER: '待注册', UNREGISTERED: '未注册', REGISTERED: '已注册', DEFERRED: '已暂缓',
    EXEMPTED: '免注册', CLOSED: '已关闭', BLOCKED: '暂不可办'
  }
  return map[String(status || '').toUpperCase()] || status || '待确认'
}
function eligibilityText(status) {
  const map = { ELIGIBLE: '符合', INELIGIBLE: '不符合', PENDING: '待核验' }
  return map[String(status || '').toUpperCase()] || status || '待核验'
}
function deferralText(deferral) {
  const status = String(deferral.status || '').toUpperCase()
  const map = { PENDING: '审核中', APPROVED: '已批准', RETURNED: '已退回', REJECTED: '未通过' }
  return `${map[status] || deferral.status || '待处理'}${deferral.reason ? ` · ${deferral.reason}` : ''}`
}
function canDefer(batch) {
  return !uncertainDeferralKeys.value.includes(String(batch.batchId)) && String(deferReasons[batch.batchId] || '').trim().length >= 2
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => ['REGISTER_TERM', 'DEFER_REGISTRATION'].includes(item.action))
  uncertainDeferralKeys.value = pending.filter((item) => item.action === 'DEFER_REGISTRATION').map((item) => item.objectId)
  uncertainRegistrations.value = Object.fromEntries(pending.filter((item) => item.action === 'REGISTER_TERM').map((item) => [item.objectId, { registrationId: item.ackId }]))
  for (const reference of pending) {
    const current = batches.value.find((item) => String(item.batchId || '') === reference.objectId)
    const formal = reference.action === 'REGISTER_TERM'
      ? reference.ackId && String(current?.registrationId || '') === reference.ackId && current?.registrationStatus === 'REGISTERED'
      : reference.ackId && String(current?.deferral?.deferralId || '') === reference.ackId
    if (formal && guard.completePersistentCommand(reference)) {
      actionReceipt.value = { batchId: reference.objectId, batchName: current?.batchName || '原注册批次', result: reference.action === 'REGISTER_TERM' ? '本学期注册已完成' : deferralText(current.deferral), operatedAt: current?.registeredAt || current?.deferral?.createdAt || current?.deferral?.submittedAt, next: reference.action === 'REGISTER_TERM' ? '核对本学期课表与已选课程是否已经同步' : '请继续跟踪学校受理结果。' }
    } else {
      actionReceipt.value = { batchId: reference.objectId, batchName: current?.batchName || '原注册批次', result: reference.action === 'REGISTER_TERM' ? '原注册结果待确认' : '原暂缓申请结果待确认', next: reference.ackId ? formal ? '正式记录已读到，但本地待确认引用未能安全清理；刷新不会自动再次提交。' : '尚未读取到原回执对应的本人正式记录；刷新不会自动再次提交。' : '原提交未取得服务端回执编号；刷新不会自动再次提交。' }
    }
  }
  const remaining = guard.pendingCommands().filter((item) => ['REGISTER_TERM', 'DEFER_REGISTRATION'].includes(item.action))
  uncertainDeferralKeys.value = remaining.filter((item) => item.action === 'DEFER_REGISTRATION').map((item) => item.objectId)
  uncertainRegistrations.value = Object.fromEntries(remaining.filter((item) => item.action === 'REGISTER_TERM').map((item) => [item.objectId, { registrationId: item.ackId }]))
}
async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicRegistration())
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '注册批次读取失败，请稍后重试')
    loading.value = false
    return false
  }
  data.value = read.value || { batches: [] }
  reconcilePersistentCommands()
  for (const batch of batches.value) {
    if (deferReasons[batch.batchId] == null) deferReasons[batch.batchId] = ''
  }
  loading.value = false
  return true
}
async function register(batch) {
  const command = pendingRegistration.value
  if (!command || command !== batch || !guard.isCurrentCommand(command) || command.canRegister !== true || actingId.value || uncertainRegistrations.value[command.batchId]) return
  const persistent = guard.preparePersistentCommand({ action: 'REGISTER_TERM', objectId: command.batchId })
  if (!persistent) { actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: '注册未发送', next: '浏览器无法保存待确认引用，请检查本地存储后再提交。' }; return }
  actingId.value = `register:${command.batchId}`
  uncertainRegistrations.value = { ...uncertainRegistrations.value, [command.batchId]: { registrationId: '' } }
  try {
    const result = await portalApi.academicRegistrationRegister(command.batchId)
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = result?.batchId == null || String(result.batchId) === command.batchId ? guard.rememberPersistentAck(persistent, result?.registrationId) : null
    const id = acknowledged?.ackId || ''
    uncertainRegistrations.value[command.batchId] = { registrationId: id }
    pendingRegistration.value = null
    actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: '注册结果待确认', next: '正在核对本次正式注册编号；确认前不要重复提交。' }
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    const current = batches.value.find(item => String(item.batchId) === command.batchId)
    const confirmed = id && String(current?.registrationId || '') === id && current?.registrationStatus === 'REGISTERED'
    const committed = confirmed && persistentCommandCleared(persistent)
    if (committed) delete uncertainRegistrations.value[command.batchId]
    actionReceipt.value = {
      batchId: command.batchId, batchName: command.batchName,
      result: committed ? '本学期注册已完成' : '注册结果待确认',
      operatedAt: current?.registeredAt || '学校未提供办理时间',
      next: committed ? '核对本学期课表与已选课程是否已经同步' : confirmed ? '正式记录已读到，但本地待确认引用未能安全清理；确认前不要重复提交。' : '请刷新当前批次核对原注册记录，确认前不要重复提交。'
    }
    if (committed) markStudentAcademicFormClean()
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    const kind = studentAcademicWriteErrorKind(e)
    if (!['network', 'forbidden'].includes(kind)) {
      guard.completePersistentCommand(persistent)
      if (persistentCommandCleared(persistent)) delete uncertainRegistrations.value[command.batchId]
    }
    if (kind === 'forbidden') { clearSensitive(e); return }
    actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: kind === 'network' ? '注册结果待确认' : '注册未完成', next: academicErrorMessage(e, '请重新核对。') }
    if (kind === 'network' || kind === 'conflict') await load()
    else ui.notify(academicErrorMessage(e, '注册失败'))
  } finally {
    if (guard.isCurrentCommand(command)) actingId.value = ''
  }
}
function openRegisterConfirm(batch) {
  if (batch?.canRegister !== true || actingId.value || uncertainRegistrations.value[String(batch.batchId)]) return
  pendingRegistration.value = guard.beginCommand({ batchId: String(batch.batchId), batchName: batch.batchName || '当前批次', eligibilityStatus: batch.eligibilityStatus, canRegister: true })
}
function closeRegisterConfirm() {
  if (actingId.value) return
  pendingRegistration.value = null
}
async function submitDefer(batch) {
  if (!batch?.canDefer || !canDefer(batch) || actingId.value) return
  const command = guard.beginCommand({ batchId: String(batch.batchId), batchName: batch.batchName || '当前批次', reason: String(deferReasons[batch.batchId] || '').trim(), requestedUntil: deferUntil[batch.batchId] || '' })
  if (!await systemConfirm({ title: '确认暂缓注册', message: `确认对“${command.batchName}”提交暂缓注册申请？`, confirmText: '提交暂缓申请' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'DEFER_REGISTRATION', objectId: command.batchId })
  if (!persistent) { actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: '暂缓申请未发送', next: '浏览器无法保存待确认引用，请检查本地存储后再提交。' }; return }
  actingId.value = `defer:${command.batchId}`
  try {
    const result = await portalApi.academicRegistrationDefer(command.batchId, {
      reason: command.reason,
      ...(command.requestedUntil ? { requestedUntil: command.requestedUntil } : {})
    })
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.deferralId)
    uncertainDeferralKeys.value = [...new Set([...uncertainDeferralKeys.value, command.batchId])]
    actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: '暂缓申请结果待确认', next: '正在读取本人正式暂缓申请，确认前不要重复提交。' }
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    const current = batches.value.find((item) => String(item.batchId) === command.batchId)
    const formal = current?.deferral
    // 后端契约使用 deferralId；同批次的旧同事由记录不能归因给本次暂缓申请。
    const resultId = acknowledged?.ackId
    const confirmed = formal && resultId && String(formal.deferralId) === String(resultId)
    if (confirmed && persistentCommandCleared(persistent)) {
      actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: deferralText(formal), operatedAt: formal.createdAt || formal.submittedAt, next: '注册状态不会自动改为完成，请在本页跟踪学校受理结果。' }
      uncertainDeferralKeys.value = uncertainDeferralKeys.value.filter(value => value !== command.batchId)
      if (String(deferReasons[command.batchId] || '').trim() === command.reason && (deferUntil[command.batchId] || '') === command.requestedUntil) { deferReasons[command.batchId] = ''; delete deferUntil[command.batchId]; if (deferBatchId.value === command.batchId) deferBatchId.value = '' }
      markStudentAcademicFormClean()
    } else {
      uncertainDeferralKeys.value = [...new Set([...uncertainDeferralKeys.value, command.batchId])]
      actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: '暂缓申请结果待确认', next: '尚未读取到匹配的正式暂缓申请，请刷新核对，勿重复提交。' }
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    const kind = studentAcademicWriteErrorKind(e)
    if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
    if (kind === 'network' || kind === 'conflict') uncertainDeferralKeys.value = [...new Set([...uncertainDeferralKeys.value, command.batchId])]
    if (kind === 'network' || kind === 'conflict') { actionReceipt.value = { batchId: command.batchId, batchName: command.batchName, result: kind === 'network' ? '暂缓申请结果待确认' : '注册事实已变化', next: academicErrorMessage(e, '已保留申请理由，请重新核对。') }; await load() }
    else ui.notify(academicErrorMessage(e, '暂缓申请提交失败'))
  } finally {
    if (guard.isCurrentCommand(command)) actingId.value = ''
  }
}

function clearSensitive(e) {
  guard.invalidate()
  data.value = { batches: [] }; pendingRegistration.value = null; Object.keys(deferReasons).forEach((key) => delete deferReasons[key])
  actionReceipt.value = null; deferBatchId.value = ''; Object.keys(deferUntil).forEach(key => delete deferUntil[key])
  loading.value = false; actingId.value = ''
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.definition { margin:14px 0; }
.form-notice { margin-top:14px; }
.confirm-backdrop { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 24px; background: rgb(15 23 42 / 48%); backdrop-filter: blur(3px); }
.confirm-dialog { width: min(520px, 100%); padding: 24px; border: 1px solid var(--line); border-radius: 18px; background: var(--surface, #fff); box-shadow: 0 24px 70px rgb(15 23 42 / 22%); }
.confirm-dialog__eyebrow { color: var(--pri); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
.confirm-dialog h2 { margin: 8px 0; color: var(--t1); font-size: 20px; }
.confirm-dialog > p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.confirm-dialog dl { display: grid; gap: 8px; margin: 18px 0; }
.confirm-dialog dl div { display: flex; justify-content: space-between; gap: 16px; padding: 10px 12px; border-radius: 10px; background: var(--bg2); }
.confirm-dialog dt { color: var(--t4); font-size: 12px; }
.confirm-dialog dd { margin: 0; color: var(--t1); font-size: 13px; font-weight: 700; text-align: right; }
.confirm-dialog footer { display: flex; justify-content: flex-end; gap: 10px; }

</style>
