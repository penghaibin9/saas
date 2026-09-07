<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="贷款回执核验" subtitle="待办台账" show-back />
    <MobileGlobalState :state="state" :description="listError" @retry="load">
      <view v-if="state === 'ready'" class="page-pad stack">
        <view v-if="focusId" class="row-between"><text>当前记录 · {{ focusId }}</text><button class="btn btn-secondary" @click="clearFocus">返回办理队列</button></view>
        <scroll-view v-else class="loan__filters" scroll-x><button v-for="item in statuses" :key="item.value || 'all'" class="loan__filter" :class="{ on: status === item.value }" @click="changeStatus(item.value)">{{ item.label }} {{ count(item.value) }}</button></scroll-view>
        <view v-if="!focusId" class="loan__search"><input v-model.trim="keyword" class="input" maxlength="100" placeholder="姓名、学号或经办银行" confirm-type="search" @confirm="search" /><button class="btn btn-secondary" :disabled="refreshing" @click="search">查询</button></view>
        <view v-if="items.length" class="stack">
          <view v-for="item in items" :key="item.loanId" class="card loan__item">
            <view class="row-between"><view class="flex-1"><text class="loan__student">{{ item.realName }} · {{ item.studentNo }}</text><text class="card-title">{{ typeLabel(item.loanType) }} · {{ item.yearCode }}</text><text class="hint">{{ money(item.amount) }}<template v-if="item.bankName"> · {{ item.bankName }}</template><template v-if="item.bankLast4"> · 尾号 {{ item.bankLast4 }}</template></text></view><MobileStatusTag :status="item.status" :label="item.statusLabel || statusLabel(item.status)" /></view>
            <view class="loan__receipt"><text>{{ item.receiptCodeMasked || '回执编号待补充' }}</text><text v-if="item.receiptFile" class="link" @click="openFile(item)">{{ item.receiptFile.fileName || '查看回执' }}</text></view>
            <text v-if="item.reviewOpinion" class="loan__opinion" :class="{ 'loan__opinion--returned': item.status === 'RETURNED' }">{{ item.reviewOpinion }}</text>
            <view v-if="item.status === 'CONFIRMED'" class="loan__result"><text>校内回执台账已确认</text><text>记录 {{ item.loanId }} · {{ item.confirmedAt ? new Date(item.confirmedAt).toLocaleString('zh-CN', { hour12: false }) : '时间待核对' }}</text><text>银行放款请以经办银行结果为准。</text></view>
            <view class="loan__actions"><button v-if="allows(item, 'SUBMIT_RECEIPT')" class="btn btn-secondary" :disabled="!!busy" @click="openAction(item, 'SUBMIT_RECEIPT')">补录回执</button><button v-if="allows(item, 'VERIFY')" class="btn btn-primary" :disabled="!!busy" @click="openAction(item, 'VERIFY')">核验通过</button><button v-if="allows(item, 'RETURN')" class="btn btn-danger" :disabled="!!busy" @click="openAction(item, 'RETURN')">退回</button><button v-if="allows(item, 'CONFIRM')" class="btn btn-primary" :disabled="!!busy" @click="confirmRecord(item)">确认台账</button><text v-if="!item.allowedActions?.length" class="hint">只读</text></view>
          </view>
          <text v-if="moreError" class="loan__error">{{ moreError }}</text><button v-if="items.length < total" class="btn btn-secondary" :disabled="refreshing" @click="loadItems(true)">{{ moreError ? '重试加载' : '加载更多' }}</button>
        </view>
        <MobileGlobalState v-else state="empty" :title="focusId ? '该记录不存在或不在当前权限范围内' : '当前没有匹配记录'" description="切换状态或修改搜索条件后再试。" />
      </view>
    </MobileGlobalState>

    <view v-if="actionTarget" class="loan__mask" @click.self="closeAction"><view class="card loan__sheet">
      <text class="card-title">{{ actionTitle }}</text><text class="hint">{{ actionTarget.realName }} · {{ actionTarget.studentNo }} · {{ actionTarget.yearCode }}</text>
      <template v-if="actionType === 'SUBMIT_RECEIPT'"><view class="loan__form"><view class="fld"><text class="lbl">贷款类型</text><picker mode="selector" :range="loanTypes" range-key="label" :value="loanTypeIndex" @change="form.loanType = loanTypes[$event.detail.value].value"><view class="input loan__picker">{{ typeLabel(form.loanType) }}</view></picker></view><view class="fld"><text class="lbl">贷款学年</text><input v-model.trim="form.yearCode" class="input" maxlength="9" /></view><view class="fld"><text class="lbl">金额（元）</text><input v-model="form.amount" class="input" type="digit" /></view><view class="fld"><text class="lbl">经办银行</text><input v-model.trim="form.bankName" class="input" maxlength="100" /></view><view class="fld"><text class="lbl">银行卡后4位</text><input v-model.trim="form.bankLast4" class="input" type="number" maxlength="4" /></view><view class="fld"><text class="lbl">电子回执编号</text><input v-model.trim="form.receiptCode" class="input" maxlength="64" :placeholder="actionTarget.receiptCodeMasked ? '留空沿用原编号' : '请输入完整编号'" /></view><MobileAttachmentPicker class="loan__attachment" :file-ids="fileIds" biz-purpose="LOAN" label="更新回执材料" :max-count="1" :disabled="!!busy" @update:fileIds="fileIds = $event" @update:ready="fileReady = $event" @error="attachmentError" /></view></template>
      <view v-else class="fld"><text class="lbl">{{ actionType === 'RETURN' ? '退回原因（5–1000字）' : '核验备注（选填）' }}</text><textarea v-model.trim="reason" class="ta" maxlength="1000" :placeholder="actionType === 'RETURN' ? '写清需要学生修改的信息或材料' : '可记录核对结果'" /></view>
      <text v-if="actionError" class="loan__error">{{ actionError }}</text><view class="loan__sheet-actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeAction">取消</button><button class="btn btn-primary flex-1" :disabled="!!busy || !actionValid" @click="submitAction">确认{{ actionType === 'RETURN' ? '退回' : actionType === 'VERIFY' ? '核验' : '提交' }}</button></view>
    </view></view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import fileSdk from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() { return { state: 'loading', focusId: '', requestSeq: 0, listError: '', moreError: '', items: [], total: 0, statusCounts: {}, page: 1, status: 'RECEIPT', keyword: '', appliedKeyword: '', refreshing: false, busy: '', actionTarget: null, actionType: '', actionError: '', reason: '', form: {}, fileIds: [], fileReady: true, statuses: [{ value: 'RECEIPT', label: '待核验' }, { value: 'REGISTERED', label: '待补回执' }, { value: 'RETURNED', label: '已退回' }, { value: 'VERIFIED', label: '已核验' }, { value: '', label: '全部' }], loanTypes: [{ value: 'ORIGIN', label: '生源地贷款' }, { value: 'CAMPUS', label: '校园地贷款' }] } },
  computed: {
    actionTitle() { return ({ SUBMIT_RECEIPT: '补录贷款回执', VERIFY: '核验贷款回执', RETURN: '退回学生修改' })[this.actionType] || '处理贷款记录' },
    loanTypeIndex() { return Math.max(0, this.loanTypes.findIndex(item => item.value === this.form.loanType)) },
    actionValid() { if (this.actionType === 'RETURN') return this.reason.length >= 5 && this.reason.length <= 1000; if (this.actionType === 'VERIFY') return true; const year = /^(\d{4})-(\d{4})$/.exec(this.form.yearCode || ''); const amount = Number(this.form.amount); return !!year && Number(year[2]) === Number(year[1]) + 1 && amount >= 1000 && amount <= 20000 && (!this.form.bankLast4 || /^\d{4}$/.test(this.form.bankLast4)) && (!!String(this.form.receiptCode || '').replace(/\s+/g, '') || !!this.actionTarget?.receiptCodeMasked) && this.fileReady }
  },
  onLoad(options) { this.focusId = String(options?.recordId || ''); this.load() }, onUnload() { this.requestSeq++ }, onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) }, onBackPress() { if (this.actionTarget) { this.closeAction(); return true } return false },
  methods: {
    clearFocus() { uni.redirectTo({ url: '/pages/teacher/affairs/loan/index' }) },
    allows(item, action) { return Array.isArray(item && item.allowedActions) && item.allowedActions.includes(action) }, count(status) { return Number(this.statusCounts[status || 'ALL'] || 0) }, typeLabel(type) { return type === 'CAMPUS' ? '校园地贷款' : '生源地贷款' }, statusLabel(status) { return ({ REGISTERED: '待补回执', RECEIPT: '待学校核验', RETURNED: '已退回修改', VERIFIED: '学校已核验', CONFIRMED: '台账已确认', WITHDRAWN: '已撤回' })[status] || '状态待确认' }, money(value) { if (value === null || value === undefined || value === '') return '—'; if (String(value).includes('*')) return '金额已隐藏'; return Number.isFinite(Number(value)) ? `¥${Number(value).toFixed(2)}` : '—' },
    load() { return this.loadItems() },
    async loadItems(more = false) {
      more = more === true
      if (more && (this.refreshing || this.items.length >= this.total)) return
      const request = ++this.requestSeq
      const page = more ? this.page + 1 : 1
      this.refreshing = true; this.listError = ''; this.moreError = ''
      if (!more) this.state = 'loading'
      try {
        if (this.focusId && !/^[1-9]\d*$/.test(this.focusId)) throw new Error('贷款记录编号无效，请返回办理队列')
        const data = await teacherApi.getAffairsLoans(this.focusId ? { recordId: this.focusId, page: 1, pageSize: 1 } : { page, pageSize: 20, status: this.status, keyword: this.appliedKeyword })
        if (request !== this.requestSeq) return
        if (!Array.isArray(data?.items)) throw new Error('列表暂不可用，请重试')
        this.items = more ? [...new Map([...this.items, ...data.items].map(item => [String(item.loanId), item])).values()] : data.items
        this.total = Number(data.total || 0); this.statusCounts = data.statusCounts || {}
        this.page = page; this.state = 'ready'
      } catch (e) {
        if (request !== this.requestSeq) return
        if (more) this.moreError = '加载失败，已加载记录仍保留，请重试'
        else { this.listError = normalizeError(e).text || '列表加载失败，请重试'; this.state = 'error' }
      } finally { if (request === this.requestSeq) this.refreshing = false }
    }, search() { this.appliedKeyword = this.keyword.trim(); return this.loadItems() }, changeStatus(value) { if (this.status === value) return; this.status = value; return this.loadItems() },
    openAction(item, action) { this.actionTarget = item; this.actionType = action; this.reason = ''; this.actionError = ''; this.form = { loanType: item.loanType || 'ORIGIN', yearCode: item.yearCode || '', amount: item.amount || '', bankName: item.bankName || '', bankLast4: item.bankLast4 || '', receiptCode: '' }; this.fileIds = item.receiptFile?.fileId ? [item.receiptFile.fileId] : []; this.fileReady = !this.fileIds.length }, closeAction() { if (!this.busy) this.actionTarget = null }, attachmentError(error) { this.actionError = normalizeError(error).text || '回执材料处理失败' },
    actionPayload() { const base = { action: this.actionType, version: this.actionTarget.version }; if (this.actionType === 'RETURN' || this.actionType === 'VERIFY') return { ...base, reason: this.reason }; return { ...base, loanType: this.form.loanType, yearCode: this.form.yearCode, amount: String(this.form.amount), bankName: this.form.bankName || undefined, bankLast4: this.form.bankLast4 || undefined, receiptCode: this.form.receiptCode.replace(/\s+/g, '') || undefined, receiptFileId: this.fileIds[0] || undefined } },
    async runAction(item, body) { if (this.busy) return; this.busy = `${body.action}-${item.loanId}`; this.actionError = ''; try { await teacherApi.actAffairsLoan(item.loanId, body); toast('贷款记录已更新'); this.actionTarget = null; await this.loadItems() } catch (e) { this.actionError = normalizeError(e).text || '处理失败，请刷新后重试'; toast(this.actionError) } finally { this.busy = '' } }, submitAction() { if (!this.actionTarget || !this.actionValid) return; return this.runAction(this.actionTarget, this.actionPayload()) }, confirmRecord(item) { uni.showModal({ title: '确认贷款台账？', content: `${item.realName} · ${item.yearCode} · ${this.money(item.amount)}`, confirmText: '确认台账', success: res => { if (res.confirm) this.runAction(item, { action: 'CONFIRM', version: item.version }) } }) }, async openFile(item) { if (!item.receiptFile?.fileId) return; this.busy = `file-${item.loanId}`; try { await fileSdk.open(item.receiptFile.fileId) } catch (e) { toast(normalizeError(e).text || '回执材料读取失败') } finally { this.busy = '' } }
  }
}
</script>

<style scoped>
.loan__item .card-title,.loan__item .hint{display:block}.loan__opinion.loan__opinion--returned{color:#8a3d20;background:#fff5ed}
.loan__result{display:flex;flex-direction:column;gap:6px;padding-top:10px;border-top:1px solid var(--border-light);font-size:12px;color:var(--text-secondary)}
.loan__filters { white-space:nowrap; }.loan__filter { display:inline-flex; margin-right:8px; padding:8px 12px; border:1px solid var(--border-light); border-radius:18px; color:var(--text-secondary); background:var(--bg-card); font-size:12px; }.loan__filter.on { border-color:var(--brand-primary); color:#fff; background:var(--brand-primary); }.loan__search { display:flex; gap:8px; }.loan__search .input { flex:1; }.loan__item { display:flex; flex-direction:column; gap:10px; }.loan__student { display:block; color:var(--text-secondary); font-size:12px; }.loan__receipt { display:flex; justify-content:space-between; gap:10px; padding:9px 10px; border-radius:9px; color:var(--text-secondary); background:var(--bg-page); font-size:12px; }.loan__opinion { padding:8px 10px; border-radius:8px; color:var(--text-secondary); background:var(--bg-page); font-size:12px; }.loan__actions { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; }.loan__actions .btn { margin:0; font-size:12px; }.loan__mask { position:fixed; z-index:1000; inset:0; display:flex; align-items:flex-end; background:rgba(15,23,42,.52); }.loan__sheet { width:100%; max-height:90vh; overflow:auto; padding:18px; border-radius:18px 18px 0 0; }.loan__form { display:grid; grid-template-columns:1fr 1fr; gap:0 10px; }.loan__attachment { grid-column:1 / -1; margin-top:12px; }.loan__picker { display:flex; align-items:center; }.loan__error { display:block; margin-top:8px; color:var(--danger-600); font-size:12px; }.loan__sheet-actions { display:flex; gap:10px; margin-top:14px; }
</style>
