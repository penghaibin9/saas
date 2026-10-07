<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="学生评教" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="ev__notice"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <text class="ev__hint">仅展示本人正式教学班内的课程。答卷匿名保存，提交后不可重复提交。</text>
        <view class="list-group" v-if="d.list && d.list.length">
          <view v-for="t in d.list" :key="t.taskId" class="list-row ev__item" :class="{ 'is-target': String(t.taskId) === targetId }">
            <view class="flex-1">
              <text class="t-md">{{ t.courseName || '课程' }}</text>
              <text class="ev__sub">{{ t.teacherName || '教师' }} · {{ t.batchName || '评教批次' }}</text>
              <text v-if="t.submitted" class="ev__state is-done">本人已匿名提交</text>
              <text v-else-if="t.canSubmit" class="ev__state is-open">评教窗口开放中</text>
              <text v-else class="ev__state">当前不可提交 · {{ statusText(t.windowStatus) }}</text>
            </view>
            <button
              v-if="t.canSubmit"
              class="btn btn-primary btn-sm"
              :disabled="submitting || !!pendingApplication"
              @click="openSubmit(t)"
            >
              {{ submitting ? '提交中…' : '去评教' }}
            </button>
            <text v-else class="ev__done">{{ t.submitted ? '已完成' : '不可提交' }}</text>
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无评教任务" description="教务处发布且本人进入正式教学班名单后，课程会出现在此。" />
        <view v-if="d.pagination.total > 0 || page > 1" class="ev__pager">
          <button class="btn" :disabled="page <= 1 || state === 'loading'" @click="changePage(page - 1)">上一页</button>
          <text>第 {{ page }} / {{ pageCount }} 页，共 {{ d.pagination.total }} 项</text>
          <button class="btn" :disabled="!d.pagination.hasMore || state === 'loading'" @click="changePage(page + 1)">下一页</button>
        </view>
      </view>
    </AcademicPageState>

    <view v-if="active" class="ev__mask" @click="closeForm">
      <view class="ev__sheet card stack-sm" @click.stop>
        <text class="ev__sheet-title">评价 · {{ active.courseName }}</text>
        <text class="ev__sub">授课教师 {{ active.teacherName || '—' }}（匿名）</text>
        <view class="ev__score-row">
          <text class="ev__label">综合分（0-100）</text>
          <input :disabled="submitting || !!pendingApplication" class="ev__input" type="number" v-model="score" placeholder="如 90" />
        </view>
        <textarea :disabled="submitting || !!pendingApplication" class="ev__textarea" v-model="comment" maxlength="200"
                  placeholder="选填：意见建议（匿名进入教务统计）" />
        <text class="ev__privacy">提交后只展示本人“已完成”状态，不向学生端返回匿名答卷内容。</text>
        <button class="btn btn-primary" :disabled="!canSubmit || !!submitting || !!pendingApplication" @click="submit">
          {{ submitting ? '提交中…' : '匿名提交' }}
        </button>
        <button class="btn btn-ghost" :disabled="!!submitting" @click="closeForm">保存草稿并返回</button>
      </view>
    </view>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { academicApplicationPage } from './application-page'
import { savePending } from './pending-ledger'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
const STATUS = { OPEN: '开放中', CLOSED: '已关闭', PENDING: '待开放' }
const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const PAGE_SIZE = 20
function normalizePagination(value, requestedPage) {
  const page = value?.page
  const pageSize = value?.pageSize
  const total = value?.total
  const hasMore = value?.hasMore
  if (!Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || hasMore !== page * pageSize < total) {
    throw new Error('评教任务分页信息无法核对')
  }
  return { page, pageSize, total, hasMore }
}
export default {
  components: { AcademicPageNav, AcademicPageState },
mixins: [academicApplicationPage],
  created() { this.applicationScope = 'evaluation' },
  data() { return { d: null, state: 'loading', active: null, score: '', comment: '', targetId: '', drafts: {}, page: 1, academicDraftFields: ['active', 'score', 'comment', 'drafts'] } },
  computed: {
    canSubmit() { const n = Number(this.score); return this.active && this.active.canSubmit === true && this.score !== '' && Number.isFinite(n) && n >= 0 && n <= 100 },
    pageCount() { return this.d?.pagination?.total ? Math.ceil(this.d.pagination.total / PAGE_SIZE) : 1 }
  },
  onLoad(options = {}) { this.targetId = String(options.id || ''); this.load() },
  onHide() { this.saveDraft() },
  methods: {
    statusText(status) { return STATUS[status] || '窗口未开放' },
    resetAcademicContext() { this.clearApplicationContext(); this.active = null; this.drafts = {}; this.score = ''; this.comment = ''; this.targetId = ''; this.page = 1 },
    clearForbiddenEvaluationContext() {
      const hadPending = this.protectPendingReference()
      this.d = null
      this.active = null
      this.drafts = {}
      this.score = ''
      this.comment = ''
      this.targetId = ''
      this.page = 1
      this.clearApplicationContext()
      savePending('draft:' + this.applicationScope, null)
      if (hadPending) this.applicationNotice = '当前无权核对评教任务；本次匿名提交仍待核实。'
    },
    finishApplication() {
      if (this.active) { const next = { ...this.drafts }; delete next[String(this.active.taskId)]; this.drafts = next }
      this.active = null; this.score = ''; this.comment = ''
      this.applicationNotice = '已核对学校记录：本课程评教已完成。'
    },
    load(requestedPage = this.page) {
      const page = Number(requestedPage)
      if (!Number.isSafeInteger(page) || page < 1) return Promise.resolve(null)
      const identity = currentSessionGeneration()
      return this.readAcademic(async () => {
        const epoch = this.readEpoch
        try {
          return await studentApi.getMyEvaluationTasks({ page, pageSize: PAGE_SIZE, taskId: this.targetId || undefined })
        } catch (error) {
          if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenEvaluationContext()
          throw error
        }
      }, d => {
        if (!Array.isArray(d.list) || d.list.length > PAGE_SIZE) throw new Error('评教信息无法核对')
        const pagination = normalizePagination(d.pagination, page)
        if (d.list.length > 0 && pagination.total < (pagination.page - 1) * PAGE_SIZE + d.list.length) {
          throw new Error('评教任务分页记录不完整')
        }
        this.d = { ...d, pagination }
        this.page = pagination.page
        if (this.active) {
          const latest = d.list.find(t => String(t.taskId) === String(this.active.taskId))
          this.active = latest || { ...this.active, canSubmit: false }
        }
        this.acceptApplication(d.list, 'taskId', row => row.submitted === true)
        if (this.targetId) { const task = d.list.find(t => String(t.taskId) === this.targetId); if (task) this.openSubmit(task); this.targetId = '' }
      })
    },
    changePage(page) { return this.load(page) },
    openSubmit(t) {
      if (!t || t.canSubmit !== true || t.submitted || this.submitting || this.pendingApplication) return
      this.saveDraft(); this.active = t
      const draft = this.drafts[String(t.taskId)] || { score: '', comment: '' }
      this.score = draft.score; this.comment = draft.comment
    },
    saveDraft() { if (this.active) this.drafts = { ...this.drafts, [String(this.active.taskId)]: { score: this.score, comment: this.comment } } },
    closeForm() { if (!this.submitting) { this.saveDraft(); this.active = null } },
    submit() {
      if (!this.canSubmit || this.submitting || this.pendingApplication) return
      this.saveDraft()
      const taskId = this.active.taskId
      return this.sendApplication({ title: '确认提交评价：' + this.active.courseName, body: { taskId, objectiveScore: Number(this.score), comment: this.comment.trim() || undefined, answers: { overall: Number(this.score) } },
        existingId: taskId, recovery: { field: 'submitted', equals: true }, send: body => studentApi.submitEvaluation(body), rows: this.d.list, idKey: 'taskId' })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.ev__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.ev__item { align-items: center; gap: var(--space-2); }
.ev__item.is-target { border: 1px solid var(--brand-primary); box-shadow: 0 0 0 2px var(--brand-50); }
.ev__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ev__state { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.ev__state.is-open { color: var(--primary-600); }
.ev__state.is-done { color: var(--success-600); }
.ev__done { flex-shrink: 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ev__pager { display:flex; align-items:center; justify-content:space-between; gap:var(--space-2); color:var(--text-tertiary); font-size:var(--font-size-xs); }
.ev__pager .btn { flex:1; margin:0; }
.ev__mask { position: fixed; inset: 0; background: var(--bg-mask); display: flex; align-items: flex-end; z-index: 200; }
.ev__sheet { width: 100%; border-radius: var(--radius-lg) var(--radius-lg) 0 0; padding: var(--space-4); }
.ev__sheet-title { font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); }
.ev__score-row { display: flex; align-items: center; gap: var(--space-2); }
.ev__label { font-size: var(--font-size-sm); color: var(--text-secondary); white-space: nowrap; }
.ev__input { flex: 1; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 8px 10px; }
.ev__textarea { width: 100%; min-height: 80px; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 8px 10px; box-sizing: border-box; }
.btn-sm { padding: 4px 10px; font-size: var(--font-size-xs); }
.ev__privacy { color: var(--text-tertiary); font-size: 12px; line-height: 1.5; }
.ev__notice { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border-radius: var(--radius-md); background: var(--success-50); color: var(--success-700); font-size: 12px; }
.ev__notice.is-warning { background: var(--warning-50); color: var(--warning-700); }
.ev__notice text:first-child { font-size: 14px; font-weight: 700; }
</style>
