<template>
  <div class="loan-student"><div v-if="recordId" class="loan-head"><strong>贷款记录 {{ recordId }}</strong><button class="sp-btn sp-btn--ghost" @click="clearFocus">全部记录</button></div>
    <section class="sp-card loan-head">
      <div><strong>助学贷款回执</strong><span>{{ activeCount }} 笔办理中</span></div>
      <button class="sp-btn" type="button" :disabled="loading || !!busy" @click="openCreate">提交回执</button>
    </section>

    <div v-if="error" class="loan-error" role="alert">
      <span>{{ error }}</span><button class="sp-btn sp-btn--ghost" type="button" @click="load">重试</button>
    </div>
    <StateBlock v-else-if="loading" type="loading" text="正在同步贷款办理进度…" />
    <section v-else class="sp-card loan-list">
      <header><strong>我的贷款记录</strong><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="load">刷新</button></header>
      <StateBlock v-if="!visibleItems.length" type="empty" :text="recordId ? '未找到这笔贷款记录，请核对入口或返回全部记录' : '还没有助学贷款回执记录'" />
      <article v-for="item in visibleItems" :key="item.loanId" class="loan-row">
        <div class="loan-main">
          <strong>{{ typeLabel(item.loanType) }} · {{ item.yearCode }}</strong>
          <span>{{ money(item.amount) }}<template v-if="item.bankName"> · {{ item.bankName }}</template><template v-if="item.bankLast4"> · 尾号 {{ item.bankLast4 }}</template></span>
        </div>
        <div class="loan-receipt">
          <span>{{ item.receiptCodeMasked || '回执编号待补充' }}</span>
          <button v-if="item.receiptFile" type="button" :disabled="busy === `file-${item.loanId}`" @click="openFile(item)">{{ item.receiptFile.fileName || '查看回执' }}</button>
        </div>
        <div class="loan-state"><StatusTag :text="item.statusLabel || statusLabel(item.status)" :tone="statusTone(item.status)" /><small v-if="item.reviewOpinion">{{ item.reviewOpinion }}</small></div>
        <div class="loan-actions">
          <button v-if="allows(item, 'RESUBMIT')" class="sp-btn" type="button" :disabled="!!busy" @click="openEdit(item)">{{ item.status === 'REGISTERED' ? '补充回执' : '修改后重提' }}</button>
          <button v-if="allows(item, 'WITHDRAW')" class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="withdrawTarget = item">撤回</button>
          <span v-if="!item.allowedActions?.length">{{ nextHint(item.status) }}</span>
        </div>
        <div v-if="item.status === 'CONFIRMED'" class="loan-result"><strong>校内回执台账已确认</strong><span>记录 {{ item.loanId }} · {{ item.confirmedAt ? new Date(item.confirmedAt).toLocaleString('zh-CN', { hour12: false }) : '时间待核对' }}</span><span>学校核验完成，银行放款请以经办银行结果为准。</span></div>
      </article>
    </section>

    <div v-if="drawer.visible" class="loan-mask" @click.self="closeDrawer">
      <section class="sp-card loan-dialog" role="dialog" aria-modal="true" aria-labelledby="loan-form-title">
        <header><div><strong id="loan-form-title">{{ drawer.item ? '修改贷款回执' : '提交贷款回执' }}</strong><span>年度额度 1,000–20,000 元</span></div><button type="button" aria-label="关闭" @click="closeDrawer">×</button></header>
        <div class="loan-form">
          <label><span>贷款类型</span><select v-model="form.loanType" class="sp-inp" :disabled="!!busy"><option value="ORIGIN">生源地贷款</option><option value="CAMPUS">校园地贷款</option></select></label>
          <label><span>贷款学年</span><input v-model.trim="form.yearCode" class="sp-inp" maxlength="9" placeholder="2026-2027" :disabled="!!busy" /></label>
          <label><span>贷款金额（元）</span><input v-model="form.amount" class="sp-inp" type="number" min="1000" max="20000" step="0.01" :disabled="!!busy" /></label>
          <label><span>经办银行</span><input v-model.trim="form.bankName" class="sp-inp" maxlength="100" placeholder="如：国家开发银行" :disabled="!!busy" /></label>
          <label><span>银行卡后4位</span><input v-model.trim="form.bankLast4" class="sp-inp" maxlength="4" inputmode="numeric" placeholder="选填" :disabled="!!busy" /></label>
          <label><span>电子回执编号</span><input v-model.trim="form.receiptCode" class="sp-inp" maxlength="64" :placeholder="drawer.item?.receiptCodeMasked ? `留空沿用 ${drawer.item.receiptCodeMasked}` : '请输入完整回执编号'" :disabled="!!busy" /></label>
          <FundingAttachments
            :key="attachmentEpoch" class="loan-file" biz-type="LOAN" :max-count="1" title="电子回执材料"
            description="可上传一份 PDF、图片或文档。" :initial-files="attachments.items" :disabled="!!busy"
            @change="Object.assign(attachments, $event)"
          />
        </div>
        <label class="loan-confirm"><input v-model="form.confirm" type="checkbox" :disabled="!!busy" />我已核对贷款学年、金额和电子回执编号。</label>
        <p v-if="formError" class="field-error" role="alert">{{ formError }}</p>
        <footer><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="closeDrawer">取消</button><button class="sp-btn" type="button" :disabled="!!busy || !formValid" @click="submit">{{ busy ? '正在提交…' : '提交待核验' }}</button></footer>
      </section>
    </div>

    <div v-if="withdrawTarget" class="loan-mask" @click.self="withdrawTarget = null">
      <section class="sp-card loan-dialog loan-dialog--small" role="alertdialog" aria-modal="true">
        <h3>撤回这笔回执？</h3><p class="sp-muted">撤回后本次记录结束；如需办理，可重新提交。</p>
        <footer><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="withdrawTarget = null">继续保留</button><button class="sp-btn" type="button" :disabled="!!busy" @click="withdraw">确认撤回</button></footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FundingAttachments from './FundingAttachments.vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { fileSdk } from '../../services/fileSdk'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const items = ref([])
const route = useRoute(); const router = useRouter()
const recordId = computed(() => String(route.query.recordId || ''))
const visibleItems = computed(() => recordId.value ? items.value.filter(item => String(item.loanId) === recordId.value) : items.value)
function clearFocus(){ const query = { ...route.query }; delete query.recordId; router.replace({ path: route.path, query }) }
const policy = ref({ minAmount: '1000.00', maxAmount: '20000.00' })
const busy = ref('')
const formError = ref('')
const drawer = reactive({ visible: false, item: null })
const withdrawTarget = ref(null)
const attachments = reactive({ fileIds: [], ready: true, hasDraft: false, busy: false, items: [] })
const attachmentEpoch = ref(0)
const academicYear = () => { const d = new Date(); const start = d.getMonth() >= 7 ? d.getFullYear() : d.getFullYear() - 1; return `${start}-${start + 1}` }
const freshForm = () => ({ loanType: 'ORIGIN', yearCode: academicYear(), amount: '', bankName: '国家开发银行', bankLast4: '', receiptCode: '', confirm: false })
const form = reactive(freshForm())

const activeCount = computed(() => items.value.filter(item => !['CONFIRMED', 'WITHDRAWN'].includes(item.status)).length)
const formValid = computed(() => {
  const amount = Number(form.amount); const year = /^(\d{4})-(\d{4})$/.exec(form.yearCode)
  const hasReceipt = !!form.receiptCode.replace(/\s+/g, '') || !!drawer.item?.receiptCodeMasked
  return !!year && Number(year[2]) === Number(year[1]) + 1 && amount >= Number(policy.value.minAmount || 1000) && amount <= Number(policy.value.maxAmount || 20000) && (!form.bankLast4 || /^\d{4}$/.test(form.bankLast4)) && hasReceipt && form.confirm && attachments.ready && !attachments.busy
})
const allows = (item, action) => Array.isArray(item?.allowedActions) && item.allowedActions.includes(action)
const typeLabel = type => type === 'CAMPUS' ? '校园地贷款' : '生源地贷款'
const statusLabel = status => ({ REGISTERED: '待补回执', RECEIPT: '待学校核验', RETURNED: '已退回修改', VERIFIED: '学校已核验', CONFIRMED: '台账已确认', WITHDRAWN: '已撤回' })[status] || '状态待确认'
const statusTone = status => ({ RECEIPT: 'warn', RETURNED: 'danger', VERIFIED: 'success', CONFIRMED: 'success' })[status] || 'default'
const nextHint = status => ({ RECEIPT: '等待学校核验', VERIFIED: '等待确认台账', CONFIRMED: '办理完成', WITHDRAWN: '流程已结束' })[status] || '等待处理'
const money = value => Number.isFinite(Number(value)) ? `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'

function resetAttachments(initial = []) { Object.assign(attachments, { fileIds: initial.map(x => x.fileId), ready: initial.every(x => x.readyForBusiness), hasDraft: initial.length > 0, busy: false, items: initial }); attachmentEpoch.value++ }
function openCreate() { drawer.item = null; Object.assign(form, freshForm()); resetAttachments(); formError.value = ''; drawer.visible = true }
function openEdit(item) { drawer.item = item; Object.assign(form, { loanType: item.loanType || 'ORIGIN', yearCode: item.yearCode || academicYear(), amount: item.amount || '', bankName: item.bankName || '', bankLast4: item.bankLast4 || '', receiptCode: '', confirm: false }); resetAttachments(item.receiptFile ? [{ ...item.receiptFile, key: 1, name: item.receiptFile.fileName || '电子回执材料' }] : []); formError.value = ''; drawer.visible = true }
function closeDrawer() { if (!busy.value) drawer.visible = false }
function payload() { return { loanType: form.loanType, yearCode: form.yearCode, amount: String(form.amount), bankName: form.bankName || undefined, bankLast4: form.bankLast4 || undefined, receiptCode: form.receiptCode.replace(/\s+/g, '') || undefined, receiptFileId: attachments.fileIds[0] || undefined, confirm: true, ...(drawer.item ? { version: drawer.item.version } : {}) } }
function validate() {
  if (!/^(\d{4})-(\d{4})$/.test(form.yearCode)) return '贷款学年应为 YYYY-YYYY'
  if (!formValid.value) return attachments.busy || !attachments.ready ? '回执材料仍在安全检查，请稍后重试' : '请核对学年、1000–20000元金额、回执编号和本人确认'
  return ''
}
async function load() { loading.value = true; error.value = ''; try { const data = await portalApi.affairsLoans(); items.value = data?.items || []; policy.value = data?.policy || policy.value } catch (e) { error.value = e?.message || '贷款记录加载失败' } finally { loading.value = false } }
async function submit() {
  formError.value = validate(); if (formError.value) return
  busy.value = drawer.item ? `resubmit-${drawer.item.loanId}` : 'submit'
  try { if (drawer.item) await portalApi.affairsLoanResubmit(drawer.item.loanId, payload()); else await portalApi.affairsLoanSubmit(payload()); ui.notify(drawer.item ? '回执已重新提交' : '回执已提交，等待学校核验'); drawer.visible = false; await load() }
  catch (e) { formError.value = e?.message || '提交失败，请重试' } finally { busy.value = '' }
}
async function withdraw() { const item = withdrawTarget.value; if (!item) return; busy.value = `withdraw-${item.loanId}`; try { await portalApi.affairsLoanWithdraw(item.loanId, item.version); ui.notify('贷款回执已撤回'); withdrawTarget.value = null; await load() } catch (e) { ui.notify(e?.message || '撤回失败，请刷新后重试') } finally { busy.value = '' } }
async function openFile(item) { const file = item.receiptFile; if (!file?.fileId) return; busy.value = `file-${item.loanId}`; try { await fileSdk.download(file.fileId, file.fileName || '电子回执') } catch (e) { ui.notify(e?.message || '回执材料读取失败') } finally { busy.value = '' } }

const registerWorkspaceForm = inject('registerWorkspaceForm', null)
const unregister = registerWorkspaceForm?.(() => drawer.visible && (!!form.receiptCode || !!form.amount || attachments.hasDraft), () => !!busy.value)
onMounted(load)
onBeforeUnmount(() => unregister?.())
</script>

<style scoped>
.loan-result{grid-column:1/-1;display:grid;gap:6px;padding-top:12px;border-top:1px solid var(--line);color:var(--t2);font-size:13px}
.loan-student { display: grid; gap: 12px; }.loan-head { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; }.loan-head div { display: flex; gap: 10px; align-items: baseline; }.loan-head strong { color: var(--t1); font-size: 16px; }.loan-head span { color: var(--t3); font-size: 12px; }.loan-list { overflow: hidden; padding: 0; }.loan-list > header { display: flex; justify-content: space-between; align-items: center; min-height: 48px; padding: 0 16px; border-bottom: 1px solid var(--line); }.loan-row { display: grid; grid-template-columns: minmax(230px,1.2fr) minmax(160px,1fr) minmax(140px,.8fr) auto; gap: 16px; align-items: center; min-height: 76px; padding: 12px 16px; border-bottom: 1px solid var(--line); }.loan-row:last-child { border-bottom: 0; }.loan-main,.loan-receipt,.loan-state { display: grid; gap: 4px; min-width: 0; }.loan-main strong { color: var(--t1); font-size: 14px; }.loan-main span,.loan-receipt span,.loan-state small,.loan-actions > span { overflow: hidden; color: var(--t3); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.loan-receipt button { overflow: hidden; padding: 0; border: 0; color: var(--pri); background: transparent; text-align: left; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }.loan-actions { display: flex; justify-content: flex-end; gap: 7px; }.loan-error { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border: 1px solid #f1b9b9; border-radius: 10px; color: #9a2929; background: #fff7f7; }.loan-mask { position: fixed; z-index: 2200; inset: 0; display: grid; place-items: center; padding: 20px; background: rgba(13,18,28,.52); }.loan-dialog { width: min(650px,100%); max-height: calc(100vh - 40px); overflow: auto; padding: 18px; }.loan-dialog--small { width: min(420px,100%); }.loan-dialog > header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }.loan-dialog > header div { display: grid; gap: 4px; }.loan-dialog > header strong { color: var(--t1); font-size: 17px; }.loan-dialog > header span { color: var(--t3); font-size: 12px; }.loan-dialog > header button { width: 34px; height: 34px; border: 0; border-radius: 8px; color: var(--t2); background: var(--bg); font-size: 22px; cursor: pointer; }.loan-form { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px 16px; }.loan-form > label { display: grid; gap: 6px; color: var(--t2); font-size: 13px; }.loan-file { grid-column: 1 / -1; }.loan-confirm { display: flex; gap: 8px; align-items: flex-start; margin-top: 14px; color: var(--t2); font-size: 13px; }.loan-dialog > footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
@media (max-width: 900px) { .loan-row { grid-template-columns: 1fr 1fr; }.loan-actions { justify-content: flex-start; } }
@media (max-width: 640px) { .loan-row,.loan-form { grid-template-columns: 1fr; }.loan-head div { display: grid; gap: 2px; }.loan-actions { flex-wrap: wrap; } }
</style>
