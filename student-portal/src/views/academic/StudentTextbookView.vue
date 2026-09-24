<template>
  <div data-academic-page class="sp-page academic-prototype textbook-page">
    <AcademicPrototypeHeader :title="signRecord ? '教材签收确认' : '教材领用'" group="培养与毕业" :object="!!signRecord" description="核对教材发放记录，收到实物后再确认签收。" :loading="loading || !!actingId" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人教材发放记录…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="signRecord">
        <AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>{{ signRecord.textbookName || signRecord.bookName }} · 本人发放记录</h2></header><form class="card-body" @submit.prevent="received && sign(signRecord)">
          <div class="form-grid"><label class="field"><span>发放对象</span><input class="input" :value="recordKey(signRecord)" readonly /></label><label class="field"><span>应收数量</span><input class="input" :value="(signRecord.qty ?? signRecord.quantity ?? '待确认') + ' 册'" readonly /></label><label class="field full"><span><input v-model="received" type="checkbox" class="check" /> 我已实际收到上述教材，书目与数量一致。</span></label></div>
          <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>没有领到不要确认。签收不是在线支付，不将费用状态同步改为已付。</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="signRecordId = ''; received = false">返回教材记录</button><button class="btn primary" :disabled="!received || !!actingId || !canSign(signRecord)">{{ actingId ? '提交中…' : '确认本人已收到' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>签收表示已实际领取教材，不代表教材费已经支付。</span></div>
        <StateBlock v-if="!records.length" type="empty" text="暂无本人教材发放记录" />
        <div class="grid-equal"><section v-for="record in records" :key="recordKey(record)" class="card"><header class="card-head"><h2>{{ record.textbookName || record.bookName || '教材名称待补充' }}</h2></header><div class="card-body">
          <div class="row"><div class="iconbox"><AcademicPrototypeIcon name="book" /></div><div><small>ISBN {{ record.isbn || '未提供' }}</small><div>{{ record.qty ?? record.quantity ?? '数量待确认' }} 册 · {{ record.termCode || '本人教材' }}</div></div></div>
          <dl class="definition"><dt>领取地点</dt><dd>{{ record.location || record.pickupLocation || '以学校发放通知为准' }}</dd><dt>签收状态</dt><dd><span class="tag" :class="canSign(record) ? 'amber' : ['SIGNED', 'RECEIVED'].includes(rawStatus(record)) ? 'green' : 'gray'">{{ statusText(record) }}</span></dd><dt v-if="record.receivedAt || record.signedAt">签收时间</dt><dd v-if="record.receivedAt || record.signedAt">{{ dateTime(record.receivedAt || record.signedAt) }}</dd><dt>费用状态</dt><dd>以学校费用台账为准，当前不提供线上付款</dd></dl>
          <footer v-if="canSign(record)" class="form-foot"><button class="btn primary" @click="signRecordId = recordKey(record); received = false">核对并签收</button></footer>
        </div></section></div>
        <section v-if="Object.keys(fees).length" class="card pad"><div class="row wrap"><small>学校教材费用台账</small><span>应收 {{ amountText(fees.totalDue) }}</span><span>已付 {{ amountText(fees.totalPaid) }}</span><span>未付 {{ amountText(fees.unpaid) }}</span></div></section>
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
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'textbook-sign')
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const records = ref([])
const fees = ref({})
const receipt = ref(null)
const receiptTone = ref('success')
const signRecordId = ref('')
const received = ref(false)
const pendingRecordIds = ref([])
const blockedRecordIds = ref([])
let pageIdentity = ''
let actingToken = 0
let actingIdentity = ''
const signRecord = computed(() => records.value.find(record => recordKey(record) === signRecordId.value))


function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records || data.distributions)) || []
}
function recordKey(record) { return String(record.recordId || record.distributionRecordId || record.id || `${record.isbn || record.textbookName}:${record.batchId || ''}`) }
function recordIdOf(record) { return exactPositiveDecimalId(record?.recordId || record?.distributionRecordId || record?.id) }
function rawStatus(record) { return String(record.status || record.signStatus || record.distributionStatus || '').toUpperCase() }
function canSign(record) {
  const id = recordIdOf(record)
  const status = rawStatus(record)
  return !!id && !pendingRecordIds.value.includes(id) && !record.receivedAt && !record.signedAt && ['DISTRIBUTED', 'ISSUED', 'PENDING'].includes(status)
}
function statusText(record) {
  const status = rawStatus(record)
  const map = { PENDING: '待签收', DISTRIBUTED: '待签收', ISSUED: '待签收', SIGNED: '已签收', RECEIVED: '已签收', RETURNED: '已退领', CANCELLED: '已取消', EXCLUDED: '不在本次领用范围' }
  if (!status && record.signedAt) return '已签收'
  return map[status] || status || (canSign(record) ? '待签收' : '待确认')
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
function amountText(value) {
  if (value == null || value === '') return '待确认'
  const amount = Number(value)
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : '待确认'
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
function keepPendingAfterDeleteFailure(record) {
  receiptTone.value = 'waiting'
  receipt.value = academicReceipt({ title: '原教材签收结果待确认', object: record?.textbookName || record?.bookName || '原教材发放记录', status: '已读取正式记录，但本地待确认引用未能安全清除', next: '请只查询本人正式记录；确认本地引用已安全清除前，不会再次签收。' })
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => item.action === 'SIGN_TEXTBOOK')
  pendingRecordIds.value = [...new Set([...pending.map((item) => item.objectId), ...blockedRecordIds.value])]
  for (const reference of pending) {
    const formal = reference.ackId ? records.value.find((item) => recordIdOf(item) === reference.objectId && recordIdOf(item) === reference.ackId) : null
    const signed = formal && ['RECEIVED', 'SIGNED'].includes(rawStatus(formal))
    if (signed) {
      if (guard.completePersistentCommand(reference)) {
        blockedRecordIds.value = blockedRecordIds.value.filter((value) => value !== reference.objectId)
        receiptTone.value = 'success'
        receipt.value = academicReceipt({ title: '原教材签收已通过本人正式记录确认', object: formal.textbookName || formal.bookName || '原教材发放记录', status: statusText(formal), operatedAt: formal.receivedAt || formal.signedAt, next: '签收不代表缴费；费用状态继续以学校费用台账为准。' })
        if (signRecordId.value === reference.objectId) { signRecordId.value = ''; received.value = false }
        markStudentAcademicFormClean()
      } else {
        blockedRecordIds.value = [...new Set([...blockedRecordIds.value, reference.objectId])]
        keepPendingAfterDeleteFailure(formal)
      }
    } else {
      const original = records.value.find((item) => recordIdOf(item) === reference.objectId)
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '原教材签收结果待确认', object: original?.textbookName || original?.bookName || '原教材发放记录', status: reference.ackId ? '尚未读取到原回执对应的本人记录' : '原提交未取得服务端回执编号', next: '本页只会刷新本人正式记录，不会自动再次签收；费用状态不会随签收推断为已付。' })
    }
  }
  pendingRecordIds.value = [...new Set([...guard.pendingCommands().filter((item) => item.action === 'SIGN_TEXTBOOK').map((item) => item.objectId), ...blockedRecordIds.value])]
}
async function load() {
  const identity = studentAcademicIdentity(session)
  if ((pageIdentity && pageIdentity !== identity) || (actingId.value && actingIdentity !== identity)) {
    actingToken += 1
    actingId.value = ''; actingIdentity = ''
    records.value = []; fees.value = {}; pendingRecordIds.value = []; blockedRecordIds.value = []
    receipt.value = null; signRecordId.value = ''; received.value = false
  }
  pageIdentity = identity
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicTextbook())
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '教材记录读取失败，请稍后重试')
    loading.value = false
    return false
  }
  records.value = rowsOf(read.value)
  fees.value = read.value?.fees || {}
  reconcilePersistentCommands()
  loading.value = false
  return true
}
async function sign(record) {
  const id = recordIdOf(record)
  if (!id || actingId.value || !canSign(record)) return
  const command = guard.beginCommand({ recordId: id, object: record.textbookName || record.bookName || '该教材' })
  const confirmed = await systemConfirm({ title: '确认教材签收', message: `确认本人已实际领到“${record.textbookName || record.bookName || '该教材'}”？提交后不可由学生端撤回。`, confirmText: '确认已领取' })
  if (!confirmed || !guard.isCurrentCommand(command) || actingId.value) return
  const persistent = guard.preparePersistentCommand({ action: 'SIGN_TEXTBOOK', objectId: command.recordId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '教材签收未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  pendingRecordIds.value = [...new Set([...pendingRecordIds.value, command.recordId])]
  const token = startActing(command.recordId)
  try {
    const result = await portalApi.academicTextbookSign(id)
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.recordId)
    receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '教材签收结果待确认', object: command.object, status: acknowledged ? '正在读取本人正式发放记录' : '服务端未返回可核对的签收记录编号', next: '确认前不要重复签收；签收不代表缴费。' })
    await load()
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    const kind = studentAcademicWriteErrorKind(e)
    const released = kind !== 'network' && guard.completePersistentCommand(persistent)
    if (kind !== 'network' && !released) {
      blockedRecordIds.value = [...new Set([...blockedRecordIds.value, command.recordId])]
      keepPendingAfterDeleteFailure(record)
      return
    }
    if (released) {
      blockedRecordIds.value = blockedRecordIds.value.filter((value) => value !== command.recordId)
      pendingRecordIds.value = pendingRecordIds.value.filter((value) => value !== command.recordId)
    }
    if (kind === 'network' || kind === 'conflict') { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: kind === 'network' ? '签收结果待确认' : '教材记录已变化', object: command.object, status: kind === 'network' ? '待服务器记录确认' : '本次签收未确认完成', next: academicErrorMessage(e, '请重新核对记录。') }); await load() }
    else ui.notify(academicErrorMessage(e, '教材签收失败'))
  } finally {
    finishActing(token, command.identity)
  }
}

function clearSensitive(e) {
  guard.invalidate()
  records.value = []
  fees.value = {}
  pendingRecordIds.value = []; blockedRecordIds.value = []
  receipt.value = null; signRecordId.value = ''; received.value = false
  actingId.value = ''; loading.value = false
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.definition{margin:14px 0}.form-notice{margin-top:14px}.field input.check{width:auto;accent-color:var(--pri)}</style>
