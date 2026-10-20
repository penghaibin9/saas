<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="学期注册" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="mk__notice" role="status">
          <text class="mk__notice-title">{{ applicationNotice }}</text>
          <button v-if="pendingApplication" class="btn btn-ghost btn-sm" @click="load">重新核对</button>
        </view>
        <view class="card">
          <text v-if="d.realName || d.studentNo" class="t-md">{{ [d.realName, d.studentNo].filter(Boolean).join(' · ') }}</text>
          <text class="mk__sub">注册结果以当前批次状态为准</text>
        </view>
        <AcademicPageState v-if="!(d.batches || []).length" state="empty" :title="d.note || '暂无开放批次'"
          description="教务处开放注册窗口后，可在此自助完成注册或申请暂缓。" />
        <view v-for="b in d.batches" :key="b.batchId" class="card stack-sm" :class="{ 'is-target': String(b.batchId) === targetId }">
          <text class="t-md t-bold">{{ b.batchName }}</text>
          <text class="mk__sub">{{ b.registerTypeLabel }} · {{ (b.windowStart || '').slice(0,10) }} ~ {{ (b.windowEnd || '').slice(0,10) }}</text>
          <view class="mk__state-row"><text>{{ registrationText(b.registrationStatus) }}</text><text>{{ eligibilityText(b.eligibilityStatus) }}</text></view>
          <text v-if="b.blockReason" class="mk__reason">{{ b.blockReason }}</text>
          <view v-if="b.deferral" class="mk__sub"><text>暂缓申请：{{ deferralText(b.deferral.status) }} · {{ b.deferral.reason || '请关注学校审核进度' }}</text><text v-if="b.deferral.requestedUntil">申请期限：{{ b.deferral.requestedUntil.slice(0, 10) }}</text><text v-if="b.deferral.reviewNote">学校意见：{{ b.deferral.reviewNote }}</text></view>
          <view v-if="b.registrationStatus === 'REGISTERED'" class="mk__receipt" role="status">
            <text class="mk__receipt-title">✓ 本学期注册已完成</text>
            <text class="mk__receipt-sub">注册结果已写入学籍，本批次无需重复办理。</text>
          </view>
          <view class="row-gap" style="display:flex;gap:8px;margin-top:8px">
            <button class="btn btn-primary flex-1" :disabled="!b.canRegister || submitting || !!pendingApplication" @click="doRegister(b)">{{ b.registrationStatus === 'REGISTERED' ? '已完成注册' : '完成注册' }}</button>
            <button class="btn btn-ghost flex-1" :disabled="!b.canDefer || submitting || !!pendingApplication" @click="doDefer(b)">申请暂缓</button>
          </view>
          <view v-if="deferBatchId === String(b.batchId)" class="stack-sm">
            <text class="t-sm">申请期限</text>
            <picker mode="date" :value="deferUntil" :disabled="submitting || !!pendingApplication" @change="deferUntil = $event.detail.value"><view class="mk__date">{{ deferUntil || '请选择申请暂缓至哪一天' }}</view></picker>
            <text class="t-sm">暂缓原因</text>
            <textarea :disabled="submitting || !!pendingApplication" v-model="deferReason" class="mk__defer" maxlength="500" placeholder="请填写暂缓原因，至少2字" />
            <text class="mk__sub">申请日期由学校审核，不代表自动批准或完成注册。</text>
            <button class="btn btn-primary" :disabled="submitting || !!pendingApplication || deferReason.trim().length < 2 || !deferUntil" @click="submitDefer(b)">提交暂缓申请</button>
          </view>
        </view>
        <view v-if="d.total > 0 || page > 1" class="mk__pager">
          <button class="btn" :disabled="page <= 1 || state === 'loading'" @click="changePage(page - 1)">上一页</button>
          <text>第 {{ page }} / {{ pageCount }} 页，共 {{ d.total }} 项</text>
          <button class="btn" :disabled="!d.hasMore || state === 'loading'" @click="changePage(page + 1)">下一页</button>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>
<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { academicApplicationPage } from './application-page'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { savePending } from './pending-ledger'
const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const REGISTRATION_STATUS = { REGISTERED: '已完成注册', PENDING: '待注册', PENDING_REGISTER: '待注册', UNREGISTERED: '未注册', DEFERRED: '已申请暂缓', CLOSED: '已关闭' }
const ELIGIBILITY_STATUS = { ELIGIBLE: '资格已通过', BLOCKED: '当前有待处理事项', INELIGIBLE: '当前无资格', PENDING: '资格待核对' }
const PAGE_SIZE = 20
function normalizePagination(value, requestedPage) {
  const page = value?.page
  const pageSize = value?.pageSize
  const total = value?.total
  const hasMore = value?.hasMore
  if (!Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || hasMore !== page * pageSize < total) {
    throw new Error('注册批次分页信息无法核对')
  }
  return { page, pageSize, total, hasMore }
}
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicApplicationPage],
  created() { this.applicationScope = 'registration' },
  data() { return { d: null, state: 'loading', targetId: '', deferBatchId: '', deferReason: '', deferUntil: '', page: 1, academicDraftFields: ['deferBatchId', 'deferReason', 'deferUntil'] } },
  computed: {
    pageCount() { return this.d?.total ? Math.ceil(this.d.total / PAGE_SIZE) : 1 }
  },
  onLoad(options = {}) { this.targetId = String(options.id || ''); this.load() },
  methods: {
    restorePendingDraft(pending) { if (pending.kind === 'defer') { this.deferBatchId = String(pending.body.batchId); this.deferReason = pending.body.reason; this.deferUntil = pending.body.requestedUntil || '' } },
    deferralText(value) { return { PENDING: '待学校审核', SUBMITTED: '已提交', APPROVED: '已批准暂缓', REJECTED: '未批准' }[value] || '状态待核对' },
    registrationText(value) { return REGISTRATION_STATUS[value] || '状态待确认' },
    eligibilityText(value) { return ELIGIBILITY_STATUS[value] || '资格待确认' },
    resetAcademicContext() { this.clearApplicationContext(); this.targetId = ''; this.deferBatchId = ''; this.deferReason = ''; this.deferUntil = ''; this.page = 1 },
    clearForbiddenRegistration() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.targetId = ''; this.deferBatchId = ''; this.deferReason = ''; this.deferUntil = ''; this.page = 1; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对注册记录；本次办理仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    finishApplication(kind) { this.deferBatchId = ''; this.deferReason = ''; this.deferUntil = ''; this.applicationNotice = kind === 'register' ? '已核对学校记录：本批次注册已完成。' : '已核对学校记录：暂缓申请已登记。' },
    load(requestedPage = this.page) {
      const page = Number(requestedPage)
      if (!Number.isSafeInteger(page) || page < 1) return Promise.resolve(null)
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        try { return await studentApi.getMyRegistration({ page, pageSize: PAGE_SIZE, batchId: this.targetId || undefined }) }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenRegistration(); throw error }
      }, d => {
        if (!Array.isArray(d.batches) || d.batches.length > PAGE_SIZE) throw new Error('注册记录无法核对')
        const pagination = normalizePagination(d, page)
        if (d.batches.length > 0 && pagination.total < (pagination.page - 1) * PAGE_SIZE + d.batches.length) throw new Error('注册批次分页记录不完整')
        this.d = { ...d, ...pagination }
        this.page = pagination.page
        if (this.pendingApplication?.kind === 'defer') {
          const deferrals = d.batches.filter(batch => batch.deferral).map(batch => ({ ...batch.deferral, batchId: batch.batchId }))
          this.acceptApplication(deferrals, 'deferralId', (row, body) => !!this.pendingApplication?.returnedId && String(row.batchId) === String(body.batchId) && row.reason === body.reason && String(row.requestedUntil || '').slice(0, 10) === body.requestedUntil)
        } else {
          this.acceptApplication(d.batches, 'registrationId', (row, body) => !!this.pendingApplication?.returnedId && String(row.batchId) === String(body.batchId) && row.registrationStatus === 'REGISTERED')
        }
      })
    },
    changePage(page) { return this.load(page) },
    doRegister(b) {
      if (b.canRegister !== true || this.submitting || this.pendingApplication) return
      return this.sendApplication({ title: '确认完成学期注册', kind: 'register', body: { batchId: b.batchId }, existingId: b.batchId,
        send: async body => {
          const result = await studentApi.registerSelf(body.batchId)
          return result?.registrationId && (!result.batchId || String(result.batchId) === String(body.batchId)) ? result : null
        }, rows: this.d.batches, idKey: 'registrationId', receiptKey: 'registrationId', recordKey: 'batchId', recovery: { field: 'registrationStatus', equals: 'REGISTERED' } })
    },
    doDefer(b) {
      if (b.canDefer !== true || this.submitting || this.pendingApplication) return
      if (this.deferBatchId !== String(b.batchId)) { this.deferReason = ''; this.deferUntil = '' }
      this.deferBatchId = String(b.batchId)
    },
    submitDefer(b) {
      if (b.canDefer !== true || String(b.batchId) !== this.deferBatchId || this.deferReason.trim().length < 2 || !/^\d{4}-\d{2}-\d{2}$/.test(this.deferUntil)) return
      return this.sendApplication({ title: '提交暂缓注册申请', kind: 'defer', body: { batchId: b.batchId, reason: this.deferReason.trim(), requestedUntil: this.deferUntil },
        send: async body => { const result = await studentApi.deferRegistration(body.batchId, body.reason, body.requestedUntil); return result?.deferralId && String(result.batchId) === String(body.batchId) ? result : null }, rows: this.d.batches.filter(batch => batch.deferral).map(batch => batch.deferral), idKey: 'deferralId' })
    }
  }
}
</script>
<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.mk__defer { width: 100%; min-height: 90px; box-sizing: border-box; padding: 12px; background: var(--bg-page); border-radius: 10px; font-size: 14px; }
.mk__date { padding: 12px; border: 1px solid var(--border-base); border-radius: 8px; font-size: 14px; }
.mk__sub text { display: block; margin-top: 4px; }
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
.mk__reason { display:block; color: var(--warn-fg, #b45309); font-size: 12px; margin-top: 4px; }
.mk__receipt { margin-top: 10px; padding: 10px 12px; border: 1px solid #a7d7b4; border-radius: var(--radius-md); background: #f3fbf5; }
.mk__receipt-title { display: block; color: var(--success-700, #15803d); font-size: 14px; font-weight: 600; }
.mk__receipt-sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 12px; }
.mk__notice { padding: 12px; border-radius: var(--radius-md); background: var(--primary-50); }
.mk__notice.is-warning { background: var(--warning-50); }
.mk__notice-title { display: block; font-weight: 700; color: var(--text-primary); }
.mk__notice-desc { display: block; margin-top: 4px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.mk__state-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.mk__state-row text { padding: 3px 8px; border-radius: var(--radius-full); background: var(--bg-page); color: var(--text-secondary); font-size: 12px; }
.btn-sm { margin-top: 8px; font-size: 12px; }
.is-target { border: 1px solid var(--brand-primary); box-shadow: 0 0 0 2px var(--brand-50); }
</style>
