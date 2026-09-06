<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="助学贷款" subtitle="电子回执与核验进度" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="state === 'ready'" class="page-pad stack">
        <view class="loan__bar"><text>{{ activeCount }} 笔办理中</text><button class="btn btn-primary" :disabled="!!busy" @click="openCreate">提交回执</button></view>
        <view v-if="items.length" class="stack">
          <view v-for="item in items" :key="item.loanId" class="card loan__item">
            <view class="row-between"><view class="flex-1"><text class="card-title">{{ typeLabel(item.loanType) }} · {{ item.yearCode }}</text><text class="hint">{{ money(item.amount) }}<template v-if="item.bankName"> · {{ item.bankName }}</template><template v-if="item.bankLast4"> · 尾号 {{ item.bankLast4 }}</template></text></view><MobileStatusTag :status="item.status" :label="item.statusLabel || statusLabel(item.status)" /></view>
            <view class="loan__receipt"><text>{{ item.receiptCodeMasked || '回执编号待补充' }}</text><text v-if="item.receiptFile" class="link" @click="openFile(item)">{{ item.receiptFile.fileName || '查看回执材料' }}</text></view>
            <text v-if="item.reviewOpinion" class="loan__opinion">{{ item.reviewOpinion }}</text>
            <view class="loan__actions"><button v-if="allows(item, 'RESUBMIT')" class="btn btn-primary" :disabled="!!busy" @click="openEdit(item)">{{ item.status === 'REGISTERED' ? '补充回执' : '修改后重提' }}</button><button v-if="allows(item, 'WITHDRAW')" class="btn btn-secondary" :disabled="!!busy" @click="confirmWithdraw(item)">撤回</button><text v-if="!item.allowedActions?.length" class="hint">{{ nextHint(item.status) }}</text></view>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="还没有贷款回执" description="取得电子回执后，可在这里提交给学校核验。" />
      </view>
    </MobileGlobalState>

    <view v-if="formOpen" class="loan__mask" @click.self="closeForm"><view class="card loan__sheet">
      <view class="row-between"><view><text class="card-title">{{ editing ? '修改贷款回执' : '提交贷款回执' }}</text><text class="hint">年度额度 1,000–20,000 元</text></view><text class="loan__close" @click="closeForm">×</text></view>
      <view class="loan__form">
        <view class="fld"><text class="lbl">贷款类型</text><picker mode="selector" :range="loanTypes" range-key="label" :value="loanTypeIndex" @change="form.loanType = loanTypes[$event.detail.value].value"><view class="input loan__picker">{{ typeLabel(form.loanType) }}</view></picker></view>
        <view class="fld"><text class="lbl">贷款学年</text><input v-model.trim="form.yearCode" class="input" maxlength="9" placeholder="2026-2027" /></view>
        <view class="fld"><text class="lbl">贷款金额（元）</text><input v-model="form.amount" class="input" type="digit" placeholder="1000–20000" /></view>
        <view class="fld"><text class="lbl">经办银行</text><input v-model.trim="form.bankName" class="input" maxlength="100" placeholder="如：国家开发银行" /></view>
        <view class="fld"><text class="lbl">银行卡后4位（选填）</text><input v-model.trim="form.bankLast4" class="input" type="number" maxlength="4" /></view>
        <view class="fld"><text class="lbl">电子回执编号</text><input v-model.trim="form.receiptCode" class="input" maxlength="64" :placeholder="editing?.receiptCodeMasked ? `留空沿用 ${editing.receiptCodeMasked}` : '请输入完整回执编号'" /></view>
        <MobileAttachmentPicker class="loan__attachment" :file-ids="fileIds" biz-purpose="LOAN" label="电子回执材料" :max-count="1" :disabled="!!busy" @update:fileIds="fileIds = $event" @update:ready="fileReady = $event" @error="attachmentError" />
      </view>
      <checkbox-group @change="form.confirm = $event.detail.value.includes('confirmed')"><label class="loan__check"><checkbox class="loan__box" value="confirmed" :checked="form.confirm" color="#2468dc" /><text>我已核对贷款学年、金额和回执编号。</text></label></checkbox-group>
      <text v-if="formError" class="loan__error">{{ formError }}</text>
      <view class="loan__sheet-actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeForm">取消</button><button class="btn btn-primary flex-1" :disabled="!!busy || !formValid" @click="submit">{{ busy ? '正在提交…' : '提交待核验' }}</button></view>
    </view></view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import fileSdk from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const academicYear = () => { const d = new Date(); const start = d.getMonth() >= 7 ? d.getFullYear() : d.getFullYear() - 1; return `${start}-${start + 1}` }
const freshForm = () => ({ loanType: 'ORIGIN', yearCode: academicYear(), amount: '', bankName: '国家开发银行', bankLast4: '', receiptCode: '', confirm: false })

export default {
  data() { return { state: 'loading', items: [], policy: { minAmount: '1000.00', maxAmount: '20000.00' }, busy: '', formOpen: false, editing: null, form: freshForm(), fileIds: [], fileReady: true, formError: '', loanTypes: [{ value: 'ORIGIN', label: '生源地贷款' }, { value: 'CAMPUS', label: '校园地贷款' }] } },
  computed: {
    activeCount() { return this.items.filter(item => !['CONFIRMED', 'WITHDRAWN'].includes(item.status)).length },
    loanTypeIndex() { return Math.max(0, this.loanTypes.findIndex(item => item.value === this.form.loanType)) },
    formValid() { const year = /^(\d{4})-(\d{4})$/.exec(this.form.yearCode); const amount = Number(this.form.amount); return !!year && Number(year[2]) === Number(year[1]) + 1 && amount >= Number(this.policy.minAmount || 1000) && amount <= Number(this.policy.maxAmount || 20000) && (!this.form.bankLast4 || /^\d{4}$/.test(this.form.bankLast4)) && (!!this.form.receiptCode.replace(/\s+/g, '') || !!this.editing?.receiptCodeMasked) && this.form.confirm && this.fileReady }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) },
  onBackPress() { if (this.formOpen) { this.closeForm(); return true } return false },
  methods: {
    allows(item, action) { return Array.isArray(item && item.allowedActions) && item.allowedActions.includes(action) },
    typeLabel(type) { return type === 'CAMPUS' ? '校园地贷款' : '生源地贷款' },
    statusLabel(status) { return ({ REGISTERED: '待补回执', RECEIPT: '待学校核验', RETURNED: '已退回修改', VERIFIED: '学校已核验', CONFIRMED: '台账已确认', WITHDRAWN: '已撤回' })[status] || '状态待确认' },
    nextHint(status) { return ({ RECEIPT: '等待学校核验', VERIFIED: '等待学校确认台账', CONFIRMED: '办理完成', WITHDRAWN: '流程已结束' })[status] || '等待处理' },
    money(value) { return Number.isFinite(Number(value)) ? `¥${Number(value).toFixed(2)}` : '—' },
    async load() { this.state = 'loading'; try { const data = await studentApi.getMyLoans(); this.items = data.items || []; this.policy = data.policy || this.policy; this.state = 'ready' } catch (e) { this.state = 'error'; toast(normalizeError(e).text || '贷款记录加载失败') } },
    openCreate() { this.editing = null; this.form = freshForm(); this.fileIds = []; this.fileReady = true; this.formError = ''; this.formOpen = true },
    openEdit(item) { this.editing = item; this.form = { loanType: item.loanType || 'ORIGIN', yearCode: item.yearCode || academicYear(), amount: item.amount || '', bankName: item.bankName || '', bankLast4: item.bankLast4 || '', receiptCode: '', confirm: false }; this.fileIds = item.receiptFile?.fileId ? [item.receiptFile.fileId] : []; this.fileReady = !this.fileIds.length; this.formError = ''; this.formOpen = true },
    closeForm() { if (!this.busy) this.formOpen = false },
    attachmentError(error) { this.formError = normalizeError(error).text || '回执材料处理失败' },
    payload() { return { loanType: this.form.loanType, yearCode: this.form.yearCode, amount: String(this.form.amount), bankName: this.form.bankName || undefined, bankLast4: this.form.bankLast4 || undefined, receiptCode: this.form.receiptCode.replace(/\s+/g, '') || undefined, receiptFileId: this.fileIds[0] || undefined, confirm: true, ...(this.editing ? { version: this.editing.version } : {}) } },
    async submit() { if (!this.formValid) { this.formError = this.fileReady ? '请核对学年、1000–20000元金额、回执编号和本人确认' : '回执材料仍在安全检查'; return } this.busy = 'submit'; this.formError = ''; try { if (this.editing) await studentApi.resubmitLoan(this.editing.loanId, this.payload()); else await studentApi.submitLoan(this.payload()); toast(this.editing ? '回执已重新提交' : '回执已提交'); this.formOpen = false; await this.load() } catch (e) { this.formError = normalizeError(e).text || '提交失败，请重试' } finally { this.busy = '' } },
    confirmWithdraw(item) { uni.showModal({ title: '撤回这笔回执？', content: '撤回后本次记录结束；如需办理，可重新提交。', confirmText: '确认撤回', success: res => { if (res.confirm) this.withdraw(item) } }) },
    async withdraw(item) { this.busy = `withdraw-${item.loanId}`; try { await studentApi.withdrawLoan(item.loanId, item.version); toast('回执已撤回'); await this.load() } catch (e) { toast(normalizeError(e).text || '撤回失败') } finally { this.busy = '' } },
    async openFile(item) { if (!item.receiptFile?.fileId) return; this.busy = `file-${item.loanId}`; try { await fileSdk.open(item.receiptFile.fileId) } catch (e) { toast(normalizeError(e).text || '回执材料读取失败') } finally { this.busy = '' } }
  }
}
</script>

<style scoped>
.loan__bar { display:flex; justify-content:space-between; align-items:center; min-height:42px; color:var(--text-secondary); font-size:13px; }.loan__bar .btn { margin:0; }.loan__item { display:flex; flex-direction:column; gap:10px; }.loan__item .card-title,.loan__item .hint { display:block; }.loan__item .hint { margin-top:4px; }.loan__receipt { display:flex; justify-content:space-between; gap:12px; padding:9px 10px; border-radius:9px; color:var(--text-secondary); background:var(--bg-page); font-size:12px; }.loan__opinion { padding:8px 10px; border-radius:8px; color:#8a3d20; background:#fff5ed; font-size:12px; }.loan__actions { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }.loan__actions .btn { margin:0; }.loan__mask { position:fixed; z-index:1000; inset:0; display:flex; align-items:flex-end; background:rgba(15,23,42,.52); }.loan__sheet { width:100%; max-height:90vh; overflow:auto; padding:18px; border-radius:18px 18px 0 0; }.loan__close { padding:0 6px; color:var(--text-secondary); font-size:26px; }.loan__form { display:grid; grid-template-columns:1fr 1fr; gap:0 10px; }.loan__attachment { grid-column:1 / -1; margin-top:12px; }.loan__picker { display:flex; align-items:center; }.loan__check { display:flex; gap:8px; align-items:flex-start; margin-top:14px; color:var(--text-secondary); font-size:12px; line-height:1.5; }.loan__box { flex-shrink:0; transform:scale(.8); transform-origin:top left; }.loan__error { display:block; margin-top:8px; color:var(--danger-600); font-size:12px; }.loan__sheet-actions { display:flex; gap:10px; margin-top:14px; }
</style>
