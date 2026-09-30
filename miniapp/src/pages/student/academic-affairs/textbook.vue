<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="我的教材" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="tb__notice" role="status">
          <text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button>
        </view>
        <view class="card tb__sum">
          <view class="tb__sum-item"><text class="tb__sum-num">{{ fmt(d.fees.totalDue) }}</text><text class="tb__sum-lb">应缴(元)</text></view>
          <view class="tb__sum-item"><text class="tb__sum-num">{{ fmt(d.fees.totalPaid) }}</text><text class="tb__sum-lb">已缴</text></view>
          <view class="tb__sum-item"><text class="tb__sum-num tb__unpaid">{{ fmt(d.fees.unpaid) }}</text><text class="tb__sum-lb">待缴</text></view>
        </view>

        <view class="section-head"><text class="section-head__title">教材领用</text></view>
        <view class="list-group" v-if="d.distributions && d.distributions.length">
          <view v-for="r in d.distributions" :key="r.recordId" class="tb__object">
          <view class="list-row tb__item">
            <view class="flex-1">
              <text class="t-md">{{ r.textbookName }}<text v-if="r.qty > 1"> ×{{ r.qty }}</text></text>
              <text class="tb__sub">{{ statusText(r.status) }}<text v-if="r.receivedAt"> · {{ r.receivedAt }}</text></text>
            </view>
            <button v-if="canSign(r)" class="btn btn-sm btn-primary" :disabled="submitting || !!pendingApplication" @click="openSign(r)">
              核对并签收
            </button>
            <MobileStatusTag v-else :status="r.status" :label="statusText(r.status)" />
          </view>
          <view v-if="signingId === String(r.recordId)" class="tb__confirm">
            <text class="t-md">教材签收确认</text>
            <text class="tb__sub">书目：{{ r.textbookName }} · 应收数量：{{ r.qty ?? '待核对' }}</text>
            <text v-if="r.isbn" class="tb__sub">ISBN：{{ r.isbn }}</text>
            <text class="tb__sub">签收只确认实际领到教材，不会改变费用状态。</text>
            <checkbox-group @change="received = $event.detail.value.includes('received')"><label class="tb__check"><checkbox value="received" :checked="received" :disabled="submitting || !!pendingApplication" />我已实际收到上述教材，书目与数量一致</label></checkbox-group>
            <button class="btn btn-primary" :disabled="!received || submitting || !!pendingApplication" @click="sign(r)">确认实际收到</button>
          </view>
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无教材记录" description="学校完成教材征订发放后，这里出现你的领用与费用。" />
        <view v-if="showDistributionPagination" class="tb__pages">
          <button v-if="distributionPage > 1" class="btn" :disabled="state === 'loading'" @click="changeDistributionPage(distributionPage - 1)">上一页</button>
          <text>领用记录第 {{ distributionPage }}/{{ distributionPageCount }} 页，共 {{ d.distributionPagination.total }} 条</text>
          <button v-if="d.distributionPagination.hasMore" class="btn" :disabled="state === 'loading'" @click="changeDistributionPage(distributionPage + 1)">下一页</button>
        </view>
        <text class="tb__sub">签收表示本人已领取教材，不代表教材费已支付。</text>

        <view class="section-head" v-if="d.fees.items && d.fees.items.length"><text class="section-head__title">教材费用明细</text></view>
        <view class="list-group" v-if="d.fees.items && d.fees.items.length">
          <view v-for="f in d.fees.items" :key="f.feeId" class="list-row tb__item">
            <view class="flex-1">
              <text class="t-md">{{ f.textbookName }}</text>
              <text class="tb__sub">{{ f.status === 'WAIVED' ? '原应缴' : '应缴' }} {{ fmt(f.amount) }} 元 · 已缴 {{ fmt(f.paidAmount) }} 元</text>
            </view>
            <MobileStatusTag :status="f.status" :label="f.status === 'WAIVED' ? '已减免' : ''" />
          </view>
        </view>
        <view v-if="showFeePagination" class="tb__pages">
          <button v-if="feePage > 1" class="btn" :disabled="state === 'loading'" @click="changeFeePage(feePage - 1)">上一页</button>
          <text>费用明细第 {{ feePage }}/{{ feePageCount }} 页，共 {{ d.fees.total }} 条</text>
          <button v-if="d.fees.pagination.hasMore" class="btn" :disabled="state === 'loading'" @click="changeFeePage(feePage + 1)">下一页</button>
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
const DIST_STATUS = { PENDING: '待签收', RECEIVED: '已领取', EXCLUDED: '当前不发放', RETURNED: '已退领', EXCHANGED: '已换领' }
const PAGE_SIZE = 20
const pageNumber = value => Math.max(1, Number(value) || 1)
const pageCount = page => Math.max(1, Math.ceil(Number(page?.total || 0) / Math.max(1, Number(page?.pageSize || PAGE_SIZE))))
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicApplicationPage],
  created() { this.applicationScope = 'textbook' },
  data() { return { d: null, state: 'loading', signingId: '', received: false } },
  computed: {
    distributionPage() { return pageNumber(this.d?.distributionPagination?.page) },
    feePage() { return pageNumber(this.d?.fees?.pagination?.page) },
    distributionPageCount() { return pageCount(this.d?.distributionPagination) },
    feePageCount() { return pageCount(this.d?.fees?.pagination) },
    showDistributionPagination() { return Number(this.d?.distributionPagination?.total || 0) > PAGE_SIZE },
    showFeePagination() { return Number(this.d?.fees?.total || 0) > PAGE_SIZE }
  },
  onLoad() { this.load() },
  onHide() { this.received = false },
  methods: {
    fmt(v) { return v == null ? '—' : Number(v).toFixed(2) },
    statusText(s) { return DIST_STATUS[s] || '待核对' },
    canSign(r) { return r.status === 'PENDING' },
    resetAcademicContext() { this.clearApplicationContext(); this.signingId = ''; this.received = false },
    clearForbiddenTextbook() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.signingId = ''; this.received = false; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对教材记录；本次签收仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    finishApplication() { this.signingId = ''; this.received = false; this.applicationNotice = '已核对学校记录：教材已签收。签收不代表已缴费。' },
    openSign(r) { if (this.submitting || this.pendingApplication || !this.canSign(r)) return; this.signingId = String(r.recordId); this.received = false },
    async load(requestedPages = {}) {
      let focusedRecordId = ''
      let resolvedPages = null
      const result = await this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        const distributionPage = pageNumber(requestedPages.distributionPage || this.d?.distributionPagination?.page)
        const feePage = pageNumber(requestedPages.feePage || this.d?.fees?.pagination?.page)
        resolvedPages = { distributionPage, feePage }
        // A cold-start after an uncertain sign only reads the exact original receipt under
        // the current student's server scope; it never scans all historical records.
        focusedRecordId = String(this.pendingApplication?.existingId || '')
        try {
          return await studentApi.getMyTextbook({
            distributionPage,
            distributionPageSize: PAGE_SIZE,
            distributionRecordId: focusedRecordId || undefined,
            feePage,
            feePageSize: PAGE_SIZE
          })
        }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenTextbook(); throw error }
      }, d => {
        if (!Array.isArray(d.distributions) || !d.fees) throw new Error('教材信息无法核对')
        const distributionPagination = {
          total: Number(d.distributionPagination?.total ?? d.distributions.length),
          page: pageNumber(d.distributionPagination?.page),
          pageSize: Number(d.distributionPagination?.pageSize || PAGE_SIZE),
          hasMore: Boolean(d.distributionPagination?.hasMore)
        }
        const fees = {
          ...d.fees,
          items: Array.isArray(d.fees.items) ? d.fees.items : [],
          total: Number(d.fees.total ?? d.fees.items?.length ?? 0),
          pagination: {
            page: pageNumber(d.fees.pagination?.page ?? d.fees.page),
            pageSize: Number(d.fees.pagination?.pageSize ?? d.fees.pageSize ?? PAGE_SIZE),
            hasMore: Boolean(d.fees.pagination?.hasMore ?? d.fees.hasMore)
          }
        }
        this.d = { ...d, distributions: d.distributions, distributionPagination, fees }
        this.acceptApplication(this.d.distributions, 'recordId', (row, body) => String(this.pendingApplication?.returnedId || '') === String(body.recordId) && row.status === 'RECEIVED')
      })
      // After a successful exact recovery, return to the original paged list rather than
      // leaving the user on a one-row recovery projection.
      if (result && focusedRecordId && !this.pendingApplication) return this.load(resolvedPages || requestedPages)
      return result
    },
    changeDistributionPage(page) { return this.load({ distributionPage: page, feePage: this.feePage }) },
    changeFeePage(page) { return this.load({ distributionPage: this.distributionPage, feePage: page }) },
    sign(r) {
      if (!this.canSign(r) || this.submitting || this.pendingApplication || !this.received || this.signingId !== String(r.recordId)) return
      return this.sendApplication({ title: '确认本人已领取：' + r.textbookName, content: `${r.textbookName}，应收${r.qty ?? '待核对'}册。请确认书目与数量一致，签收不代表已缴费。`, body: { recordId: r.recordId }, existingId: r.recordId,
        recovery: { field: 'status', equals: 'RECEIVED' }, send: body => studentApi.signTextbook(body.recordId), rows: this.d.distributions, idKey: 'recordId' })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.tb__sum { display: flex; justify-content: space-around; padding: var(--space-3) 0; }
.tb__sum-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.tb__sum-num { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-primary); }
.tb__unpaid { color: var(--danger-600); }
.tb__sum-lb { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.tb__item { align-items: center; }
.tb__confirm { display:flex; flex-direction:column; gap:12px; margin:0 12px 12px; padding:14px; border:1px solid var(--border-base); border-radius:10px; }
.tb__check { display:flex; align-items:center; min-height:44px; gap:8px; font-size:14px; line-height:1.6; }
.tb__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.btn-sm { height: 32px; line-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); }
.tb__notice { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border-radius: var(--radius-md); background: var(--success-50); color: var(--success-700); font-size: 12px; }
.tb__notice.is-warning { background: var(--warning-50); color: var(--warning-700); }
.tb__notice text:first-child { font-size: 14px; font-weight: 700; }
.tb__pages { display:flex; align-items:center; justify-content:space-between; gap:8px; color:var(--text-tertiary); font-size:12px; }
.tb__pages .btn { margin:0; min-width:72px; }
</style>
