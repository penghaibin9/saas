<template>
  <div class="consent-workspace">
    <section class="sp-card">
      <div class="sp-panel__head">知情确认任务 <button type="button" class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="loading || reading || busy" @click="loadList">刷新任务</button></div>
      <p class="sp-muted">打开学校下发的正文，核对当前实习安排；无法确认时提交原因，由学校核实后重新下发。</p>
      <StateBlock v-if="loading" type="loading" text="正在加载当前批次知情任务…" />
      <StateBlock v-else-if="error" type="error" :text="error" />
      <StateBlock v-else-if="!items.length" type="empty" text="当前批次暂无知情确认任务" />
      <div v-else class="consent-tasks">
        <button v-for="item in items" :key="item.id" type="button" class="consent-task" :aria-pressed="selected?.id === item.id" :disabled="busy" @click="openTask(item)">
          <span><strong>{{ item.consentType === 'GUARDIAN' ? '监护人知情确认' : '学生知情确认' }}</strong><small>正文版本：{{ item.contentVersion || '待核实' }}</small></span>
          <StatusTag :text="statusText(item.status)" :tone="statusTone(item.status)" />
        </button>
      </div>
    </section>
    <section class="sp-card" aria-live="polite">
      <div class="sp-panel__head">正文与办理</div>
      <p v-if="context.historyMode" class="sp-muted">历史实习记录仅供查看，不能提交确认或原因。</p>
      <div v-if="receipt" class="consent-receipt" role="status"><strong>{{ receipt.text }}</strong><p>{{ receipt.readback ? '已从学校服务重新读取同一任务。' : '办理已提交，最新结果暂未读回，请刷新任务核对。' }}</p><p v-if="receipt.reason">已提交原因：{{ receipt.reason }}</p></div>
      <StateBlock v-if="!selected" type="empty" text="请选择任务，打开正文并办理" />
      <template v-else-if="selected.consentType !== 'STUDENT'">
        <p class="sp-muted">{{ selected.consentType === 'GUARDIAN' ? '由已绑定的监护人本人办理，学生可查看进度。' : '确认人类型待学校核实，暂不能办理。' }}</p>
        <StatusTag :text="statusText(selected.status)" :tone="statusTone(selected.status)" />
      </template>
      <template v-else>
        <StateBlock v-if="reading && !detail" type="loading" text="正在读取学校保存的正文…" />
        <template v-if="detail">
          <p class="sp-muted">正文版本：{{ detail.contentVersion }} · {{ statusText(detail.status) }}</p>
          <article class="consent-document">{{ detail.contentSnapshot }}</article>
          <p class="sp-muted">已读：{{ formatTime(detail.viewedAt) }}<span v-if="detail.confirmedAt"> · 确认：{{ formatTime(detail.confirmedAt) }}</span></p>
          <p v-if="detail.status === 'REJECTED' && detail.rejectionReason" class="sp-muted">已提交原因：{{ detail.rejectionReason }}</p>
          <p v-if="reading" class="sp-muted">正在登记阅读，请稍候…</p>
          <template v-if="detail.status === 'PENDING' && !context.historyMode">
            <label class="consent-reason">无法确认原因<textarea v-model="reason" class="sp-inp" rows="3" placeholder="如无法确认，请填写具体原因（至少5个字）" :disabled="busy" /></label>
            <div class="consent-actions"><button type="button" class="sp-btn" :disabled="!canAct" @click="submit('confirm')">本人已阅读并确认</button><button type="button" class="sp-btn sp-btn--ghost" :disabled="!canAct" @click="submit('reject')">提交无法确认原因</button></div>
          </template>
          <p v-else class="sp-muted">{{ detail.status === 'REJECTED' ? '原因已交给学校核实；学校重新下发后，请打开新正文办理。' : '当前任务已结束，无需重复提交。' }}</p>
        </template>
        <p v-if="actionError" class="consent-error" role="alert">{{ actionError }}</p>
        <button v-if="!reading && (!detail || conflict)" type="button" class="sp-btn sp-btn--ghost" :disabled="busy || loading" @click="openTask(selected)">重新打开正文核对</button>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { internshipComplianceApi as api } from '../../services/internshipComplianceApi'
import { currentSessionGeneration } from '../../services/request'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'

const props = defineProps({ context: { type: Object, required: true } })
const session = useSessionStore()
const items = ref([]), selected = ref(null), detail = ref(null)
const loading = ref(false), reading = ref(false), busy = ref(false)
const error = ref(''), actionError = ref(''), reason = ref(''), conflict = ref(false), receipt = ref(null)
let alive = true, epoch = 0, listSequence = 0, detailSequence = 0
const recordId = () => String(props.context.recordId || props.context.internshipId || '')
const contextKey = () => [String(props.context.batchId || ''), recordId(), !!props.context.historyMode, session.user?.tenantId, session.user?.userId].join('|')
const capture = (id = '') => ({ epoch, generation: currentSessionGeneration(), key: contextKey(), id: String(id) })
const current = t => alive && !document.hidden && t.epoch === epoch && t.generation === currentSessionGeneration() && t.key === contextKey() && (!t.id || String(selected.value?.id) === t.id)
const canAct = computed(() => !busy.value && !reading.value && !loading.value && !error.value && !conflict.value && !props.context.historyMode && detail.value?.status === 'PENDING' && !!detail.value.viewedAt && selected.value?.consentType === 'STUDENT')
function statusText(s) { return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', REVOKED: '已作废', SUPERSEDED: '已替换，请查看新任务', EXPIRED: '已过期', NOT_APPLICABLE: '不适用' })[s] || '状态待学校核实' }
function statusTone(s) { return s === 'VALID' ? 'success' : ['REJECTED', 'REVOKED', 'EXPIRED'].includes(s) ? 'danger' : 'warn' }
function formatTime(v) {
  if (!v) return '尚未登记'
  const raw = String(v), date = new Date(/(Z|[+-]\d{2}:\d{2})$/i.test(raw) ? raw : raw + 'Z')
  return Number.isNaN(date.getTime()) ? '时间待核实' : new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)
}
function errorText(e) {
  if (e?.bizCode === 'DATA_CONFLICT') return '任务或正文已更新，原版本、正文和原因已保留。请重新打开正文核对后办理。'
  if (e?.bizCode === 'NO_PERMISSION' || e?.status === 403) return '当前账号无权办理此任务，请联系学校核实。'
  if (e?.network) return '网络连接失败，已填写的原因仍保留，请重试。'
  return '暂未完成，请核对当前任务后重试；已填写的原因仍保留。'
}
function assertTask(row, t) {
  if (!row || String(row.id) !== t.id || String(row.internshipId) !== recordId() || row.consentType !== 'STUDENT') throw new Error('Unexpected consent context')
}
function rows(data) {
  const result = Array.isArray(data) ? data : data?.items
  if (!Array.isArray(result)) throw new Error('Unexpected consent list')
  return result.filter(x => String(x.internshipId) === recordId())
}
async function loadList() {
  if (busy.value || reading.value || !props.context.batchId || !recordId() || document.hidden) return
  const t = capture(), seq = ++listSequence
  loading.value = true; error.value = ''
  try {
    const result = await api.consents(String(props.context.batchId))
    if (!current(t) || seq !== listSequence) return
    items.value = rows(result)
    if (selected.value) {
      selected.value = items.value.find(x => String(x.id) === String(selected.value.id)) || null
      detail.value = null
      if (!selected.value) reason.value = ''
    }
  } catch (e) { if (current(t) && seq === listSequence) { items.value = []; error.value = errorText(e) } }
  finally { if (current(t) && seq === listSequence) loading.value = false }
}
async function openTask(item) {
  if (!item || busy.value || loading.value || document.hidden) return
  if (String(selected.value?.id) !== String(item.id)) { reason.value = ''; receipt.value = null }
  selected.value = item; detail.value = null; actionError.value = ''; conflict.value = false
  const t = capture(item.id), seq = ++detailSequence
  if (item.consentType !== 'STUDENT') { reading.value = false; return }
  const valid = () => current(t) && seq === detailSequence
  reading.value = true
  try {
    const original = await api.consentDetail(t.id)
    if (!valid()) return
    assertTask(original, t)
    if (!String(original.contentSnapshot || '').trim()) throw new Error('Empty consent content')
    detail.value = original
    await nextTick()
    if (!valid()) return
    if (original.status === 'PENDING' && !props.context.historyMode) {
      const viewed = await api.consentView(t.id)
      if (!valid()) return
      assertTask(viewed, t)
      if (viewed.contentHash !== original.contentHash || viewed.contentVersion !== original.contentVersion || viewed.contentSnapshot !== original.contentSnapshot) throw { bizCode: 'DATA_CONFLICT' }
      detail.value = viewed
    }
  } catch (e) { if (valid()) { conflict.value = true; actionError.value = errorText(e) } }
  finally { if (valid()) reading.value = false }
}
async function submit(action) {
  if (!canAct.value || !['confirm', 'reject'].includes(action)) return
  const submittedReason = reason.value.trim()
  if (action === 'reject' && submittedReason.length < 5) { actionError.value = '请填写至少5个字的具体原因。'; return }
  const t = capture(detail.value.id), seq = detailSequence
  const body = action === 'confirm'
    ? { expectedVersion: detail.value.version, contentVersion: detail.value.contentVersion, contentHash: detail.value.contentHash, deviceDigest: 'student-portal' }
    : { expectedVersion: detail.value.version, reason: submittedReason }
  const valid = () => current(t) && seq === detailSequence
  busy.value = true; actionError.value = ''
  try {
    const accepted = await systemConfirm({ title: action === 'confirm' ? '确认当前实习知情正文' : '提交无法确认原因', message: action === 'confirm' ? `请确认已阅读正文版本“${body.contentVersion}”，并核对实习安排。` : submittedReason, confirmText: action === 'confirm' ? '本人确认' : '提交原因' })
    if (!accepted || !valid()) return
    const result = action === 'confirm' ? await api.consentConfirm(t.id, body) : await api.consentReject(t.id, body)
    if (!valid()) return
    detail.value = { ...detail.value, ...result }
    selected.value = { ...selected.value, ...result }
    receipt.value = { text: action === 'confirm' ? '本人知情确认已完成' : '无法确认原因已提交给学校', reason: action === 'reject' ? submittedReason : '', readback: false }
    try {
      const [list, reread] = await Promise.all([api.consents(String(props.context.batchId)), api.consentDetail(t.id)])
      if (!valid()) return
      assertTask(reread, t)
      items.value = rows(list); detail.value = reread
      selected.value = items.value.find(x => String(x.id) === t.id) || reread
      receipt.value.readback = true
    } catch (e) { if (valid()) actionError.value = '办理已提交，最新结果暂未读回。请刷新任务核对，不必重复提交。' }
  } catch (e) { if (valid()) { conflict.value = e?.bizCode === 'DATA_CONFLICT'; actionError.value = errorText(e) } }
  finally { if (valid()) busy.value = false }
}
function reset() {
  epoch++; listSequence++; detailSequence++
  items.value = []; selected.value = null; detail.value = null; reason.value = ''; receipt.value = null
  loading.value = false; reading.value = false; busy.value = false; error.value = ''; actionError.value = ''; conflict.value = false
}
watch(() => [contextKey(), session.token], () => { reset(); loadList() }, { immediate: true, flush: 'sync' })
function visibilityChanged() {
  epoch++; listSequence++; detailSequence++
  detail.value = null; loading.value = false; reading.value = false; busy.value = false
  if (!document.hidden) loadList()
}
onMounted(() => document.addEventListener('visibilitychange', visibilityChanged))
onBeforeUnmount(() => { alive = false; epoch++; document.removeEventListener('visibilitychange', visibilityChanged) })
</script>

<style scoped>
.consent-workspace{display:grid;grid-template-columns:minmax(240px,1fr) minmax(0,1.7fr);gap:18px;align-items:start}.consent-tasks{display:grid;gap:8px}.consent-task{display:flex;justify-content:space-between;align-items:center;gap:12px;width:100%;padding:12px;text-align:left;border:1px solid var(--line);border-radius:10px;background:var(--bg2);color:var(--t1);cursor:pointer}.consent-task[aria-pressed=true]{border-color:var(--pri);background:var(--pri-50)}.consent-task:focus-visible{outline:2px solid var(--pri);outline-offset:2px}.consent-task small{display:block;margin-top:5px;color:var(--t3)}.consent-document{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;padding:16px;border:1px solid var(--line);border-radius:10px;background:var(--bg2);color:var(--t1)}.consent-reason{display:grid;gap:8px;margin-top:18px}.consent-reason textarea{box-sizing:border-box;width:100%;resize:vertical}.consent-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.consent-error{color:var(--danger,#b42318);line-height:1.6}.consent-receipt{padding:12px;border:1px solid var(--line);border-radius:10px;margin-bottom:14px}.consent-receipt p{margin:6px 0 0;line-height:1.6;overflow-wrap:anywhere}@media(max-width:1000px){.consent-workspace{grid-template-columns:1fr}}
</style>
