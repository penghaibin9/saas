<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="勤工助学" subtitle="审核、上岗与月度考核" show-back />
    <MobileGlobalState :state="state" :description="listError" @retry="load">
      <view v-if="state === 'ready'" class="page-pad stack">
        <view v-if="!focusId" class="card wt__summary">
          <view><text class="wt__eyebrow">今日先处理</text><text class="wt__headline">{{ count('APPLIED') }} 笔待审核 · {{ count('ONBOARD') }} 人在岗</text></view>
          <text class="hint">手机端用于随时处理申请和登记月度结果；岗位发布与大批量核对建议在教师 PC 完成。</text>
        </view>
        <view v-if="!focusId" class="wt__search"><input v-model.trim="keyword" class="input" maxlength="100" placeholder="搜索学生、学号或岗位" confirm-type="search" @confirm="search" /><button class="btn btn-secondary" :disabled="refreshing" @click="search">查询</button></view>
        <scroll-view v-if="!focusId" class="wt__filters" scroll-x><button v-for="item in statuses" :key="item.value" class="wt__filter" :class="{ on: status === item.value }" @click="changeStatus(item.value)">{{ item.label }}{{ item.value ? ` ${count(item.value)}` : '' }}</button></scroll-view>
        <view v-if="focusId"><text>当前申请 · {{ focusId }}</text><button class="btn btn-secondary" @click="clearFocus">返回申请与在岗</button></view>
        <view v-if="records.length" class="stack">
          <view v-for="record in records" :key="record.recordId" class="card wt__record">
            <view class="row-between"><view class="flex-1"><text class="wt__student">{{ record.realName }} · {{ record.studentNo }}</text><text class="card-title">{{ record.post?.postName || `岗位 ${record.postId}` }}</text><text class="hint">{{ record.post?.deptName }} · {{ record.post?.workLocation || '地点待通知' }}</text></view><MobileStatusTag :status="record.status" :label="statusLabel(record.status)" /></view>
            <view class="wt__detail"><text>申请说明：{{ record.applyStatement || '未填写' }}</text><text>可工作时段：{{ record.availability || '未填写' }}</text><text>累计补贴：{{ money(record.subsidyTotal) }}</text></view>
            <text v-if="record.remark" class="hint">处理说明：{{ record.remark }}</text><text v-if="record.status === 'ONBOARD'" class="hint">已上岗，可登记月度考核。补贴登记不代表银行到账。</text>
            <view class="wt__actions"><button v-if="allows(record, 'APPROVE')" class="btn btn-primary" :disabled="!!busy" @click="confirmSimple(record)">录用</button><button v-if="allows(record, 'REJECT')" class="btn btn-danger" :disabled="!!busy" @click="openAction(record, 'REJECT')">拒绝</button><button v-if="allows(record, 'ONBOARD')" class="btn btn-primary" :disabled="!!busy" @click="openAction(record, 'ONBOARD')">核验协议并上岗</button><button v-if="allows(record, 'MONTHLY')" class="btn btn-primary" :disabled="!!busy" @click="openMonthly(record)">登记月度考核</button><button v-if="allows(record, 'TERMINATE')" class="btn btn-secondary" :disabled="!!busy" @click="openAction(record, 'TERMINATE')">结束岗位</button></view>
          </view>
          <text v-if="moreError" class="wt__error">{{ moreError }}</text><button v-if="records.length < total" class="btn btn-secondary" :disabled="refreshing" @click="loadRecords(true)">{{ moreError ? '重试加载' : '加载更多' }}</button>
        </view>
        <MobileGlobalState v-else state="empty" title="当前没有匹配记录" :description="focusId ? '该申请不存在或不在当前权限范围内。' : '可以切换状态或修改搜索条件。'" />
        <view v-if="focusId && ['ONBOARD','TERMINATED'].includes(records[0]?.status)" class="wt__detail"><text class="card-title">月度考核记录</text><text v-if="historyError">{{ historyError }}</text><button v-if="historyError" class="btn btn-secondary" @click="load">重试</button><text v-else-if="!monthlies.length">尚未登记月度考核</text><view v-for="item in monthlies" :key="item.monthlyId"><text>{{ item.monthCode }} · {{ item.workHours }}小时 · {{ ratingLabel(item.rating) }}</text><text> 登记补贴 {{ money(item.subsidyAmount) }}</text></view></view>
      </view>
    </MobileGlobalState>
    <view v-if="actionTarget" class="wt__mask" @click.self="closeAction"><view class="card wt__sheet"><text class="card-title">{{ actionTitle }}</text><text class="hint">{{ actionTarget.realName }} · {{ actionTarget.post?.postName }}</text><label v-if="actionType === 'ONBOARD'" class="wt__check" @click="agreementConfirmed = !agreementConfirmed"><text class="wt__box">{{ agreementConfirmed ? '✓' : '' }}</text><text>已核对学生与用人部门签署的勤工助学协议</text></label><view v-else class="fld"><text class="lbl">处理原因（5–500字）</text><textarea v-model.trim="reason" class="ta" maxlength="500" :placeholder="actionType === 'REJECT' ? '说明未录用原因' : '说明岗位结束原因'" /></view><text v-if="actionError" class="wt__error">{{ actionError }}</text><view class="wt__sheet-actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeAction">取消</button><button class="btn flex-1" :disabled="!!busy || !actionValid" @click="submitAction">确认{{ actionType === 'ONBOARD' ? '上岗' : actionType === 'REJECT' ? '拒绝' : '结束' }}</button></view></view></view>
    <view v-if="monthlyTarget" class="wt__mask" @click.self="closeMonthly"><view class="card wt__sheet"><text class="card-title">登记月度考核</text><text class="hint">{{ monthlyTarget.realName }} · {{ monthlyTarget.post?.postName }}</text><view class="wt__form"><view class="fld"><text class="lbl">考核月（YYYY-MM）</text><input v-model.trim="monthly.monthCode" class="input" maxlength="7" /></view><view class="fld"><text class="lbl">实际工时（0–40）</text><input v-model="monthly.workHours" class="input" type="digit" /></view><view class="fld"><text class="lbl">考核结果</text><picker mode="selector" :range="ratingOptions" range-key="label" :value="ratingIndex" @change="monthly.rating = ratingOptions[$event.detail.value].value"><view class="input wt__picker">{{ ratingLabel(monthly.rating) }}</view></picker></view><view class="fld"><text class="lbl">补贴金额（元）</text><input v-model="monthly.subsidyAmount" class="input" type="digit" /></view><view class="fld"><text class="lbl">备注（选填）</text><textarea v-model.trim="monthly.remark" class="ta" maxlength="500" /></view></view><text v-if="monthlyError" class="wt__error">{{ monthlyError }}</text><view class="wt__sheet-actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeMonthly">取消</button><button class="btn flex-1" :disabled="!!busy || !monthlyValid" @click="submitMonthly">保存考核</button></view></view></view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
export default {
  data() { return { state: 'loading', focusId: '', requestSeq: 0, monthlies: [], historyError: '', listError: '', moreError: '', records: [], total: 0, statusCounts: {}, page: 1, keyword: '', appliedKeyword: '', status: 'APPLIED', refreshing: false, busy: '', actionTarget: null, actionType: '', reason: '', agreementConfirmed: false, actionError: '', monthlyTarget: null, monthlyError: '', monthly: { monthCode: '', workHours: '', rating: 'PASS', subsidyAmount: '', remark: '' }, statuses: [{ value: '', label: '全部' }, { value: 'APPLIED', label: '待审核' }, { value: 'APPROVED', label: '已录用' }, { value: 'ONBOARD', label: '在岗' }, { value: 'TERMINATED', label: '已结束' }], ratingOptions: [{ value: 'GOOD', label: '优秀' }, { value: 'PASS', label: '合格' }, { value: 'FAIL', label: '不合格' }] } },
  computed: { actionTitle() { return this.actionType === 'ONBOARD' ? '核验协议并确认上岗' : this.actionType === 'REJECT' ? '拒绝勤工申请' : '结束勤工岗位' }, actionValid() { return this.actionType === 'ONBOARD' ? this.agreementConfirmed : this.reason.length >= 5 && this.reason.length <= 500 }, ratingIndex() { return Math.max(0, this.ratingOptions.findIndex(x => x.value === this.monthly.rating)) }, monthlyValid() { const subsidyValid = this.monthly.rating === 'FAIL' || (String(this.monthly.subsidyAmount).trim() !== '' && Number.isFinite(Number(this.monthly.subsidyAmount)) && Number(this.monthly.subsidyAmount) >= 0); return /^\d{4}-(0[1-9]|1[0-2])$/.test(this.monthly.monthCode) && String(this.monthly.workHours).trim() !== '' && Number.isFinite(Number(this.monthly.workHours)) && Number(this.monthly.workHours) >= 0 && Number(this.monthly.workHours) <= 40 && subsidyValid } },
  onLoad(options = {}) { this.focusId = String(options.recordId || ''); this.load() }, onUnload() { this.requestSeq++ }, onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) }, onBackPress() { if (this.actionTarget) { this.closeAction(); return true } if (this.monthlyTarget) { this.closeMonthly(); return true } return false },
  methods: {
    allows(row, action) { return Array.isArray(row.allowedActions) && row.allowedActions.includes(action) }, count(status) { return Number(this.statusCounts[status] || 0) }, statusLabel(s) { return ({ APPLIED: '待审核', APPROVED: '已录用', ONBOARD: '在岗', REJECTED: '未录用', WITHDRAWN: '已撤回', TERMINATED: '已结束' })[s] || '状态待确认' }, ratingLabel(s) { return ({ GOOD: '优秀', PASS: '合格', FAIL: '不合格' })[s] || '合格' }, money(value) { if (value === null || value === undefined || value === '') return '—'; if (String(value).includes('*')) return '金额已隐藏'; return Number.isFinite(Number(value)) ? `¥${Number(value).toFixed(2)}` : '—' }, currentMonth() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` },
    clearFocus() { uni.redirectTo({ url: '/pages/teacher/affairs/work-study/index' }) },
    load() { return this.loadRecords() },
    async loadRecords(more = false) {
      more = more === true
      if (more && (this.refreshing || this.records.length >= this.total)) return
      const request = ++this.requestSeq
      if (!more) { this.monthlies = []; this.historyError = '' }
      const page = more ? this.page + 1 : 1
      this.refreshing = true; this.listError = ''; this.moreError = ''
      if (!more) this.state = 'loading'
      try {
        if (this.focusId && !/^[1-9]\d*$/.test(this.focusId)) throw new Error('申请编号无效，请从待办重新打开')
        const data = await teacherApi.getWorkStudyRecords(this.focusId ? { recordId: this.focusId, page: 1, pageSize: 1 } : { page, pageSize: 20, status: this.status, keyword: this.appliedKeyword })
        if (request !== this.requestSeq) return
        if (!Array.isArray(data?.items)) throw new Error('列表暂不可用，请重试')
        this.records = more ? [...new Map([...this.records, ...data.items].map(item => [String(item.recordId), item])).values()] : data.items
        this.total = Number(data.total || 0); this.statusCounts = data.statusCounts || {}
        this.page = page; this.state = 'ready'
        if (this.focusId && ['ONBOARD','TERMINATED'].includes(this.records[0]?.status)) {
          try {
            const history = await teacherApi.getWorkStudyMonthly(this.focusId)
            if (request !== this.requestSeq) return
            if (!Array.isArray(history?.items)) throw new Error('考核记录加载失败，请重试')
            this.monthlies = history.items
          } catch (e) { if (request === this.requestSeq) this.historyError = normalizeError(e).text || '考核记录加载失败，请重试' }
        }
      } catch (e) {
        if (request !== this.requestSeq) return
        if (more) this.moreError = '加载失败，已加载记录仍保留，请重试'
        else { this.listError = normalizeError(e).text || '列表加载失败，请重试'; this.state = normalizeError(e).pageState || 'error' }
      } finally { if (request === this.requestSeq) this.refreshing = false }
    }, search() { this.appliedKeyword = this.keyword.trim(); return this.loadRecords() }, changeStatus(value) { if (this.status === value) return; this.status = value; return this.loadRecords() },
    confirmSimple(record) { uni.showModal({ title: '确认录用？', content: `录用 ${record.realName} 到“${record.post?.postName || '勤工岗位'}”？系统会校验剩余名额。`, success: (res) => { if (res.confirm) this.runAction(record, 'APPROVE', '', false) } }) }, openAction(record, action) { this.actionTarget = record; this.actionType = action; this.reason = ''; this.agreementConfirmed = false; this.actionError = '' }, closeAction() { if (!this.busy) this.actionTarget = null }, async runAction(record, action, reason, agreementConfirmed) { if (this.busy) return; this.busy = `${action}-${record.recordId}`; try { await teacherApi.actWorkStudy(record.recordId, { action, reason, version: record.version, agreementConfirmed }); toast('状态已更新'); this.actionTarget = null; await this.loadRecords() } catch (e) { const text = normalizeError(e).text || '处理失败，请刷新后重试'; this.actionError = text; toast(text) } finally { this.busy = '' } }, submitAction() { if (!this.actionTarget || !this.actionValid) return; return this.runAction(this.actionTarget, this.actionType, this.reason, this.agreementConfirmed) },
    openMonthly(record) { this.monthlyTarget = record; this.monthly = { monthCode: this.currentMonth(), workHours: '', rating: 'PASS', subsidyAmount: '', remark: '' }; this.monthlyError = '' }, closeMonthly() { if (!this.busy) this.monthlyTarget = null }, async submitMonthly() { if (this.busy) return; if (!this.monthlyTarget || !this.monthlyValid) { this.monthlyError = '请填写有效月份、0–40小时工时和非负补贴金额'; return } this.busy = `monthly-${this.monthlyTarget.recordId}`; try { await teacherApi.addWorkStudyMonthly(this.monthlyTarget.recordId, { ...this.monthly, workHours: String(this.monthly.workHours), subsidyAmount: this.monthly.rating === 'FAIL' ? '0' : String(this.monthly.subsidyAmount) }); toast('月度考核已登记'); this.monthlyTarget = null; await this.loadRecords() } catch (e) { this.monthlyError = normalizeError(e).text || '登记失败，请重试' } finally { this.busy = '' } }
  }
}
</script>

<style scoped>
.wt__record .card-title,.wt__record .hint{display:block;overflow-wrap:anywhere}

.wt__summary { display:flex; flex-direction:column; gap:6px; }.wt__eyebrow { display:block; color:var(--brand-primary); font-size:11px; font-weight:700; letter-spacing:1px; }.wt__headline { display:block; margin-top:4px; color:var(--text-primary); font-size:19px; font-weight:700; }.wt__search { display:flex; gap:8px; }.wt__search .input { flex:1; }.wt__filters { white-space:nowrap; }.wt__filter { display:inline-flex; margin-right:8px; padding:8px 12px; border:1px solid var(--border-light); border-radius:18px; color:var(--text-secondary); background:var(--bg-card); font-size:12px; }.wt__filter.on { border-color:var(--brand-primary); color:#fff; background:var(--brand-primary); }.wt__record { display:flex; flex-direction:column; gap:10px; }.wt__student { display:block; color:var(--text-secondary); font-size:12px; }.wt__detail { display:flex; flex-direction:column; gap:5px; padding:10px; border-radius:9px; color:var(--text-secondary); background:var(--bg-page); font-size:12px; line-height:1.5; }.wt__actions { display:flex; flex-wrap:wrap; gap:8px; }.wt__actions .btn { margin:0; font-size:12px; }.wt__mask { position:fixed; z-index:1000; inset:0; display:flex; align-items:flex-end; background:rgba(15,23,42,.52); }.wt__sheet { width:100%; padding:18px; border-radius:18px 18px 0 0; }.wt__check { display:flex; gap:8px; align-items:flex-start; margin-top:14px; color:var(--text-secondary); font-size:13px; line-height:1.5; }.wt__box { width:18px; height:18px; border:1px solid var(--border-default); border-radius:4px; color:var(--brand-primary); text-align:center; line-height:18px; flex-shrink:0; }.wt__form { display:grid; grid-template-columns:1fr 1fr; gap:0 10px; }.wt__form .fld:last-child { grid-column:1 / -1; }.wt__picker { display:flex; align-items:center; }.wt__error { display:block; margin-top:8px; color:var(--danger-600); font-size:12px; }.wt__sheet-actions { display:flex; gap:10px; margin-top:14px; }
</style>
