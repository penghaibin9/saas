<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="成绩复查申请" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="card"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <view class="section-head">
          <text class="section-head__title">我的复查申请</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 发起复查' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="rc__group">选择要复查的成绩</text>
          <picker mode="selector" :range="gradeLabels" :value="Math.max(0, picked)" :disabled="submitting || !!pendingApplication" @change="onGradeChange">
            <view class="rc__input rc__picker">{{ picked >= 0 ? gradeLabels[picked] : '点击选择已发布成绩' }}</view>
          </picker>
          <textarea :disabled="submitting || !!pendingApplication" class="rc__textarea" v-model="reason" :maxlength="200"
                    placeholder="复查理由（必填，≥5字，如：核对卷面分/漏统计平时分）" placeholder-class="rc__ph" />
          <button class="btn btn-primary" :disabled="!canSubmit || submitting || !!pendingApplication" @click="submit">
            {{ submitting ? '提交中…' : '提交复查申请' }}
          </button>
          <text class="rc__tip">仅可复查本人已发布成绩；同一门成绩在途复查仅限一条。</text>
        </view>

        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="r in d.items" :key="r.recheckId" class="list-row rc__item">
            <view class="flex-1">
              <text class="t-md">{{ r.courseName }}<text v-if="r.term"> · {{ r.term }}</text></text>
              <text class="rc__sub">原 {{ r.originalScore }} 分<text v-if="r.status === 'ADJUSTED'"> → 调整为 {{ r.newScore }} 分</text></text>
              <text v-if="r.reviewNote" class="rc__note">复审意见：{{ r.reviewNote }}</text>
            </view>
            <MobileStatusTag :status="r.status" :label="r.status === 'ADJUSTED' ? '成绩已调整' : ''" />
          </view>
        </view>
        <view v-if="d.total > 0 || recheckPage > 1" class="rc__pager">
          <button class="btn rc__pager-button" :disabled="recheckPage <= 1 || isPaging" @click="previousPage">上一页</button>
          <text>第 {{ recheckPage }} / {{ recheckPageCount }} 页</text>
          <button class="btn rc__pager-button" :disabled="!d.hasMore || isPaging" @click="nextPage">下一页</button>
        </view>
        <text class="rc__tip">复查申请本身不改变正式成绩，调整结果以学校审核为准。</text>
        <AcademicPageState v-if="!d.items.length" state="empty" title="暂无复查申请" description="对已发布成绩有疑问，可点击右上角发起复查。" />
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
import { academicApplicationPage } from './application-page'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { savePending } from './pending-ledger'
const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const RECHECK_PAGE_SIZE = 20

function normalizeRecheckPage(result, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== RECHECK_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || items.length > pageSize
    || (items.length > 0 && total < ((page - 1) * pageSize) + items.length)
    || hasMore !== page * pageSize < total) {
    throw new Error('复查记录分页信息无法核对')
  }
  return { ...result, items, page, pageSize, total, hasMore }
}

function mergeGrades(pageGrades, focusedGrade) {
  const rows = Array.isArray(pageGrades) ? pageGrades.slice() : []
  if (focusedGrade && focusedGrade.gradeId != null && !rows.some(row => String(row.gradeId) === String(focusedGrade.gradeId))) {
    rows.unshift(focusedGrade)
  }
  return rows
}

export default {
  components: { AcademicPageNav, AcademicPageState },
mixins: [academicApplicationPage],
  created() { this.applicationScope = 'recheck' },
  data() {
    return { d: null, grades: [], state: 'loading', showForm: false, submitting: false, picked: -1, reason: '', targetId: '', recheckPage: 1, academicDraftFields: ['reason', 'targetId', 'showForm'] }
  },
  computed: {
    gradeLabels() {
      return this.grades.map((g) => `${g.courseName}${g.term ? ' · ' + g.term : ''}（${g.score} 分）`)
    },
    canSubmit() {
      return !!this.grades[this.picked] && this.reason.trim().length >= 5
    },
    recheckPageCount() { return this.d?.total ? Math.ceil(this.d.total / RECHECK_PAGE_SIZE) : 1 },
    isPaging() { return this.state === 'loading' }
  },
  onLoad(options = {}) { this.targetId = String(options.id || ''); this.load() },
  methods: {
    prepareAcademicDraft() { this.targetId = String(this.grades[this.picked]?.gradeId || this.targetId || '') },
    restorePendingDraft(pending) { this.targetId = String(pending.body.acadGradeId); this.reason = pending.body.reason; this.showForm = true },
    resetAcademicContext() { this.clearApplicationContext(); this.grades = []; this.targetId = ''; this.recheckPage = 1; this.finishApplication() },
    clearForbiddenRecheck() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.grades = []; this.showForm = false; this.picked = -1; this.reason = ''; this.targetId = ''; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对本人复查记录；本次提交仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    finishApplication() { this.showForm = false; this.picked = -1; this.reason = '' },
    previousPage() { return this.recheckPage > 1 ? this.load(this.recheckPage - 1) : Promise.resolve(null) },
    nextPage() { return this.d?.hasMore ? this.load(this.recheckPage + 1) : Promise.resolve(null) },
    load(requested = this.pendingApplication ? 1 : this.recheckPage) {
      const requestedPage = Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1) return Promise.resolve(null)
      const selectedId = this.grades[this.picked] && this.grades[this.picked].gradeId
      const directTargetId = String(this.targetId || '').trim()
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        try {
          return await Promise.all([
            studentApi.getMyRecheck({ page: requestedPage, pageSize: RECHECK_PAGE_SIZE }),
            studentApi.getMyTranscript({ page: 1, pageSize: RECHECK_PAGE_SIZE }),
            directTargetId ? studentApi.getMyRecheckEligible(directTargetId) : Promise.resolve(null)
          ])
        }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenRecheck(); throw error }
      }, ([mine, tr, focusedGrade]) => {
          if (!tr || !Array.isArray(tr.items)) throw new Error('可复查成绩无法核对')
          this.d = normalizeRecheckPage(mine, requestedPage)
          this.recheckPage = this.d.page
          this.grades = mergeGrades(tr.items.filter((g) => g.gradeId != null), focusedGrade)
          this.picked = this.grades.findIndex(g => String(g.gradeId) === String(selectedId || this.targetId || ''))
          if (this.targetId && this.picked >= 0) { this.showForm = true; this.targetId = '' }
          this.acceptApplication(this.d.items, 'recheckId', (row, body) => !!this.pendingApplication?.returnedId && String(row.acadGradeId) === String(body.acadGradeId) && row.reason === body.reason)
      })
    },
    onGradeChange(e) { if (!this.submitting && !this.pendingApplication) this.picked = Number(e.detail.value) },
    submit() {
      if (!this.canSubmit || this.submitting || this.pendingApplication) return
      const g = this.grades[this.picked]
      if (!g) return
      return this.sendApplication({ title: `申请复查：${g.courseName}`, body: { acadGradeId: g.gradeId, reason: this.reason.trim() }, send: body => studentApi.submitRecheck(body), rows: this.d.items, idKey: 'recheckId' })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.rc__group { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; margin-top: var(--space-1); }
.rc__input { width: 100%; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.rc__picker { line-height: 40px; color: var(--text-primary); }
.rc__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.rc__ph { color: var(--text-tertiary); }
.rc__tip { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rc__item { align-items: flex-start; }
.rc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.rc__note { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: 4px; }
.rc__pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin: var(--space-4) 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.rc__pager-button { flex: 1; margin: 0; }
</style>
