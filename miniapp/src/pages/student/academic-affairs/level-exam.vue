<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="等级考试报名" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="lv__notice"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <view class="section-head"><text class="section-head__title">可报名考试</text></view>
        <view class="list-group" v-if="d.openExams && d.openExams.length">
          <view v-for="e in d.openExams" :key="e.examId">
          <view class="list-row lv__item">
            <view class="flex-1">
              <text class="t-md">{{ e.examName }}</text>
              <text class="lv__sub">{{ catLabel(e.category) }}{{ e.level ? ' · ' + e.level : '' }}{{ e.examDate ? ' · ' + e.examDate : '' }}{{ e.fee != null ? ' · 报名费¥' + e.fee : '' }}</text>
            </view>
            <button v-if="!isRegistered(e.examId)" class="btn btn-primary btn-sm" :disabled="submitting || !!pendingApplication" @click="openDetail(e)">查看并报名</button>
            <text v-else class="lv__done">已报名</text>
          </view>
          <view v-if="detailId === String(e.examId)" class="lv__detail">
            <text class="t-md">{{ e.examName }} · 报名确认</text>
            <text>报名窗口：{{ e.regStart || '以学校通知为准' }} 至 {{ e.regEnd || '以学校通知为准' }}</text>
            <text>考试安排：{{ e.examDate || '场次待学校公布' }}</text>
            <text>当前项目可发起报名，资格和最终登记由学校重新核对。</text>
            <checkbox-group @change="confirmed = $event.detail.value.includes('confirmed')"><label><checkbox value="confirmed" :checked="confirmed" :disabled="submitting || !!pendingApplication" />已核对本人资格和时间安排</label></checkbox-group>
            <button class="btn btn-primary" :disabled="!confirmed || submitting || !!pendingApplication" @click="register(e)">确认报名</button>
          </view>
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无开放报名的考试" description="等级考试开放报名后在此显示。" />
        <view v-if="d.openPagination.total > 0 || openPage > 1" class="lv__pager">
          <button class="btn lv__pager-button" :disabled="openPage <= 1 || isPaging" @click="previousOpenPage">上一页</button>
          <text>第 {{ openPage }} / {{ openPageCount }} 页，共 {{ d.openPagination.total }} 项</text>
          <button class="btn lv__pager-button" :disabled="!d.openPagination.hasMore || isPaging" @click="nextOpenPage">下一页</button>
        </view>

        <template v-if="d.myRegs && d.myRegs.length || d.registrationPagination.total > 0">
          <view class="section-head"><text class="section-head__title">我的报名</text></view>
          <view class="list-group" v-if="d.myRegs.length">
            <view v-for="r in d.myRegs" :key="r.regId" class="list-row lv__item">
              <view class="flex-1">
                <text class="t-md">{{ examName(r) }}</text>
                <text class="lv__sub">
                  {{ feeText(r.feeStatus) }}
                  <template v-if="r.status === 'SCORED'"> · {{ r.result === 'PASS' ? '通过' : '未通过' }}{{ r.score != null ? '（' + r.score + '分）' : '' }}{{ r.certNo ? ' · ' + r.certNo : '' }}</template>
                </text>
              </view>
              <MobileStatusTag :status="r.status" :label="{ REGISTERED: '已报名', SCORED: '已公布成绩' }[r.status] || ''" />
              <text v-if="r.status === 'REGISTERED' && canCancel(r)" class="lv__cancel" @click="cancel(r)">取消</text>
            </view>
          </view>
          <view class="lv__pager">
            <button class="btn lv__pager-button" :disabled="registrationPage <= 1 || isPaging" @click="previousRegistrationPage">上一页</button>
            <text>第 {{ registrationPage }} / {{ registrationPageCount }} 页，共 {{ d.registrationPagination.total }} 条</text>
            <button class="btn lv__pager-button" :disabled="!d.registrationPagination.hasMore || isPaging" @click="nextRegistrationPage">下一页</button>
          </view>
        </template>
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
const CAT = { CET: '大学英语', PUTONGHUA: '普通话', SKILL: '技能证书', OTHER: '其他' }
const LEVEL_PAGE_SIZE = 20

function normalizePagination(value, requestedPage, label) {
  const page = value?.page
  const pageSize = value?.pageSize
  const total = value?.total
  const hasMore = value?.hasMore
  if (!Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== LEVEL_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || hasMore !== page * pageSize < total) {
    throw new Error(label + '分页信息无法核对')
  }
  return { page, pageSize, total, hasMore }
}

function normalizeLevelExamPage(result, requestedOpenPage, requestedRegistrationPage) {
  const openExams = result?.openExams
  const myRegs = result?.myRegs
  if (!Array.isArray(openExams) || !Array.isArray(myRegs)
    || openExams.length > LEVEL_PAGE_SIZE || myRegs.length > LEVEL_PAGE_SIZE) {
    throw new Error('等级考试记录无法核对')
  }
  const openPagination = normalizePagination(result.openPagination, requestedOpenPage, '可报名考试')
  const registrationPagination = normalizePagination(result.registrationPagination, requestedRegistrationPage, '报名记录')
  if ((openExams.length > 0 && openPagination.total < (openPagination.page - 1) * LEVEL_PAGE_SIZE + openExams.length)
    || (myRegs.length > 0 && registrationPagination.total < (registrationPagination.page - 1) * LEVEL_PAGE_SIZE + myRegs.length)) {
    throw new Error('等级考试分页记录不完整')
  }
  return { ...result, openExams, myRegs, openPagination, registrationPagination }
}

export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicApplicationPage],
  created() { this.applicationScope = 'level-exam' },
  data() { return { d: null, state: 'loading', detailId: '', confirmed: false, openPage: 1, registrationPage: 1 } },
  computed: {
    openPageCount() { return this.d?.openPagination?.total ? Math.ceil(this.d.openPagination.total / LEVEL_PAGE_SIZE) : 1 },
    registrationPageCount() { return this.d?.registrationPagination?.total ? Math.ceil(this.d.registrationPagination.total / LEVEL_PAGE_SIZE) : 1 },
    isPaging() { return this.state === 'loading' }
  },
  onLoad() { this.load() },
  onHide() { this.confirmed = false },
  methods: {
    catLabel(c) { return CAT[c] || '等级考试' },
    resetAcademicContext() { this.clearApplicationContext(); this.detailId = ''; this.confirmed = false; this.openPage = 1; this.registrationPage = 1 },
    clearForbiddenLevelExam() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.detailId = ''; this.confirmed = false; this.openPage = 1; this.registrationPage = 1; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对报名记录；本次办理仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    finishApplication(kind) { this.detailId = ''; this.confirmed = false; this.applicationNotice = kind === 'cancel' ? '已核对学校记录：报名已取消。' : '已核对学校记录：报名已登记。缴费状态请另行核对。' },
    feeText(value) { return { PAID: '已缴费', UNPAID: '未缴费', PENDING: '待缴费', REFUNDED: '已退款', FREE: '无需缴费' }[value] || '缴费状态待核对' },
    openDetail(e) { if (this.submitting || this.pendingApplication) return; this.detailId = String(e.examId); this.confirmed = false },
    previousOpenPage() { return this.openPage > 1 ? this.load(this.openPage - 1, this.registrationPage) : Promise.resolve(null) },
    nextOpenPage() { return this.d?.openPagination?.hasMore ? this.load(this.openPage + 1, this.registrationPage) : Promise.resolve(null) },
    previousRegistrationPage() { return this.registrationPage > 1 ? this.load(this.openPage, this.registrationPage - 1) : Promise.resolve(null) },
    nextRegistrationPage() { return this.d?.registrationPagination?.hasMore ? this.load(this.openPage, this.registrationPage + 1) : Promise.resolve(null) },
    load(requestedOpenPage = this.openPage, requestedRegistrationPage = this.pendingApplication?.kind === 'cancel' ? this.registrationPage : (this.pendingApplication ? 1 : this.registrationPage)) {
      const identityChanged = this.readIdentity !== currentSessionGeneration()
      const openPage = identityChanged ? 1 : Number(requestedOpenPage)
      const registrationPage = identityChanged ? 1 : Number(requestedRegistrationPage)
      if (!Number.isSafeInteger(openPage) || !Number.isSafeInteger(registrationPage) || openPage < 1 || registrationPage < 1) return Promise.resolve(null)
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        try {
          return await studentApi.getMyLevelExam({
            openPage, openPageSize: LEVEL_PAGE_SIZE,
            registrationPage, registrationPageSize: LEVEL_PAGE_SIZE
          })
        }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenLevelExam(); throw error }
      }, d => {
        const data = normalizeLevelExamPage(d, openPage, registrationPage)
        this.d = data; this.openPage = data.openPagination.page; this.registrationPage = data.registrationPagination.page
        if (!data.openExams.some(row => String(row.examId) === this.detailId)) { this.detailId = ''; this.confirmed = false }
        this.acceptApplication(data.myRegs, 'examId', (row, body, kind) => String(this.pendingApplication?.returnedId || '') === String(body.examId) && row.status === (kind === 'cancel' ? 'CANCELLED' : 'REGISTERED'))
      })
    },
    isRegistered(id) {
      const open = (this.d?.openExams || []).find(e => String(e.examId) === String(id))
      return ['REGISTERED', 'SCORED'].includes(open?.registrationStatus)
        || (this.d?.myRegs || []).some(r => String(r.examId) === String(id) && ['REGISTERED', 'SCORED'].includes(r.status))
    },
    examName(r) { return r?.examName || (this.d?.openExams || []).find(e => String(e.examId) === String(r?.examId))?.examName || '等级考试（名称待学校核对）' },
    canCancel(r) { return r.status === 'REGISTERED' && r.examStatus === 'OPEN' },
    register(e) {
      if (this.isRegistered(e.examId) || this.submitting || this.pendingApplication || !this.confirmed || this.detailId !== String(e.examId)) return
      return this.sendApplication({ title: '确认报名：' + e.examName, body: { examId: e.examId }, existingId: e.examId,
        recovery: { field: 'status', equals: 'REGISTERED' }, send: body => studentApi.registerLevelExam(body.examId), rows: this.d.myRegs, idKey: 'examId' })
    },
    cancel(r) {
      if (!this.canCancel(r) || this.submitting || this.pendingApplication) return
      return this.sendApplication({ title: '确认取消：' + this.examName(r), kind: 'cancel', body: { examId: r.examId }, existingId: r.examId,
        recovery: { field: 'status', equals: 'CANCELLED' }, send: body => studentApi.cancelLevelExam(body.examId), rows: this.d.myRegs, idKey: 'examId' })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.lv__item { align-items: center; gap: var(--space-2); }
.lv__detail { margin:0 12px 12px; padding:14px; display:flex; flex-direction:column; gap:12px; border:1px solid var(--border-base); border-radius:10px; font-size:14px; line-height:1.6; }
.lv__detail label { display:flex; align-items:center; min-height:44px; gap:8px; }
.lv__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.lv__done { font-size: var(--font-size-xs); color: var(--success-600); }
.lv__cancel { font-size: var(--font-size-xs); color: var(--danger-600); margin-left: var(--space-2); }
.btn-sm { height: 30px; line-height: 30px; padding: 0 var(--space-3); font-size: var(--font-size-sm); }
.lv__notice { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border-radius: var(--radius-md); background: var(--success-50); color: var(--success-700); font-size: 12px; }
.lv__notice.is-warning { background: var(--warning-50); color: var(--warning-700); }
.lv__notice text:first-child { font-weight: 700; font-size: 14px; }
.lv__pager { display:flex; align-items:center; justify-content:space-between; gap:var(--space-2); margin:var(--space-3) 0; color:var(--text-secondary); font-size:var(--font-size-sm); }
.lv__pager-button { flex:1; margin:0; }
</style>
