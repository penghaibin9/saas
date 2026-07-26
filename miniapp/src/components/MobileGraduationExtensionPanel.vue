<template>
  <view v-if="visible" class="gdex">
    <view class="gdex__head">
      <view class="gdex__head-main">
        <text class="gdex__title">延期答辩与优秀成果</text>
        <text class="gdex__hint">先看状态和下一步；延期答辩与二次答辩分开处理。</text>
      </view>
      <text class="gdex__refresh" @click="load">{{ loading ? '刷新中' : '刷新' }}</text>
    </view>

    <view v-if="loading && !data" class="gdex__state"><text>正在加载当前批次扩展事项…</text></view>
    <view v-else-if="error" class="gdex__state gdex__state--error">
      <text class="gdex__error">{{ error }}。这不是“暂无业务”。</text>
      <button class="gdex__retry" @click="load">重新加载</button>
    </view>

    <template v-else-if="data">
      <view class="gdex__summary">
        <view><text>延期状态</text><text class="gdex__summary-value">{{ data.defenseDelay ? data.defenseDelay.statusLabel : '未申请' }}</text></view>
        <view><text>优秀成果</text><text class="gdex__summary-value">{{ data.excellentOutcome ? data.excellentOutcome.statusLabel : '暂无认定' }}</text></view>
        <view class="gdex__summary-wide"><text>下一步</text><text class="gdex__summary-value">{{ nextStep }}</text></view>
      </view>

      <view v-if="data.defenseDelay" class="gdex__card">
        <view class="row-between">
          <view><text class="t-md t-bold">最近一次延期申请</text><text class="gdex__sub">{{ data.defenseDelay.requestedAt || '' }}</text></view>
          <text class="gdex__status">{{ data.defenseDelay.statusLabel }}</text>
        </view>
        <text class="gdex__text">理由：{{ data.defenseDelay.reason }}</text>
        <view class="gdex__timeline">
          <text :class="{ done: data.defenseDelay.advisorReviewedBy }">导师：{{ data.defenseDelay.advisorComment || (data.defenseDelay.advisorReviewedBy ? '已处理' : '待处理') }}</text>
          <text :class="{ done: data.defenseDelay.majorReviewedBy }">专业：{{ data.defenseDelay.majorComment || (data.defenseDelay.majorReviewedBy ? '已处理' : '待处理') }}</text>
          <text :class="{ done: data.defenseDelay.collegeReviewedBy }">学院：{{ data.defenseDelay.collegeComment || (data.defenseDelay.collegeReviewedBy ? '已处理' : '待处理') }}</text>
          <text :class="{ done: data.defenseDelay.plannedDefenseDate }">排期：{{ data.defenseDelay.plannedDefenseDate ? `${data.defenseDelay.plannedDefenseDate} · ${data.defenseDelay.defenseGroupName || '答辩组待发布'}` : '待安排' }}</text>
        </view>
      </view>

      <view v-if="data.canApplyDelay" class="gdex__card gdex__card--action">
        <view class="row-between">
          <view><text class="t-md t-bold">{{ data.defenseDelay ? '重新申请延期答辩' : '申请延期答辩' }}</text><text class="gdex__sub">提交后依次由导师、专业、学院审核</text></view>
          <text class="gdex__status">可申请</text>
        </view>
        <textarea v-model="reason" class="gdex__ta" maxlength="1000" placeholder="说明延期原因、当前情况和预计准备时间（至少10字）" placeholder-class="gdex__ph" />
        <view class="gdex__submit-row">
          <text>{{ reason.trim().length }}/1000</text>
          <button class="btn btn-primary gdex__submit" :disabled="submitting || reason.trim().length < 10" @click="apply">{{ submitting ? '提交中…' : '提交延期申请' }}</button>
        </view>
      </view>
      <view v-else-if="!data.defenseDelay" class="gdex__card">
        <view class="row-between"><text class="t-md t-bold">延期答辩</text><text class="gdex__status muted">当前不可申请</text></view>
        <text class="gdex__text">仅成果检查/答辩阶段且成绩未发布时可申请。</text>
      </view>

      <view class="gdex__card">
        <view class="row-between">
          <view><text class="t-md t-bold">优秀成果认定</text><text class="gdex__sub">导师提名 → 专业复核 → 学院终审</text></view>
          <text class="gdex__status" :class="{ muted: !data.excellentOutcome }">{{ data.excellentOutcome ? data.excellentOutcome.statusLabel : '暂无记录' }}</text>
        </view>
        <template v-if="data.excellentOutcome">
          <text class="gdex__text">提名理由：{{ data.excellentOutcome.nominationReason }}</text>
          <text v-if="data.excellentOutcome.majorReviewComment" class="gdex__text">专业：{{ data.excellentOutcome.majorReviewComment }}</text>
          <text v-if="data.excellentOutcome.collegeReviewComment" class="gdex__text">学院：{{ data.excellentOutcome.collegeReviewComment }}</text>
        </template>
        <text v-else class="gdex__text">成绩优秀只是候选条件，仍须完成三级认定。</text>
      </view>
    </template>
  </view>
</template>

<script>
import { realRequest, normalizeError } from '@/services/request'
function pageStack() { return typeof getCurrentPages === 'function' ? getCurrentPages() : [] }
let owner = null
export default {
  name: 'MobileGraduationExtensionPanel',
  data() { return { visible: false, data: null, error: '', reason: '', submitting: false, loading: false, owns: false } },
  computed: {
    nextStep() {
      const delay = this.data && this.data.defenseDelay
      if (this.data && this.data.canApplyDelay) return delay ? '可重新提交延期申请' : '可提交延期申请'
      if (!delay) return '继续完成当前毕设阶段'
      const map = {
        PENDING_ADVISOR: '等待导师审核', PENDING_MAJOR: '等待专业复核',
        PENDING_COLLEGE: '等待学院审批', APPROVED: '等待学院重新排期',
        SCHEDULED: '关注答辩组重新发布', REJECTED: '按意见整改后继续流程',
        CANCELLED: '继续当前毕设流程'
      }
      return map[delay.status] || '查看审核意见'
    }
  },
  mounted() {
    const pages = pageStack(); const page = pages[pages.length - 1]
    const match = ((page && (page.route || page.__route__)) || '') === 'pages/student/graduation/index'
    if (match && owner == null) { owner = this._uid; this.owns = true; this.visible = true; this.load() }
  },
  beforeUnmount() { if (this.owns && owner === this._uid) owner = null },
  methods: {
    load() {
      if (this.loading) return
      this.loading = true; this.error = ''
      realRequest('/mobile/graduation/extensions/my').then((d) => { this.data = d })
        .catch((e) => { this.error = normalizeError(e).text || '扩展事项加载失败' })
        .finally(() => { this.loading = false })
    },
    apply() {
      const reason = this.reason.trim()
      if (reason.length < 10 || this.submitting) return
      this.submitting = true; this.error = ''
      realRequest('/mobile/graduation/defense-delay/apply', { method: 'POST', data: { reason } })
        .then(() => { this.reason = ''; uni.showToast({ title: '申请已提交', icon: 'success' }); this.load() })
        .catch((e) => { this.error = normalizeError(e).text || '延期申请提交失败' })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.gdex { margin:0 var(--page-padding-mobile) var(--space-3); padding:var(--space-3); border:1px solid var(--border-light); border-radius:var(--radius-lg); background:var(--bg-card); overflow:hidden; }
.gdex__head { display:flex; justify-content:space-between; align-items:flex-start; gap:var(--space-2); }.gdex__head-main { flex:1; min-width:0; }.gdex__title { display:block; font-size:var(--font-size-base); font-weight:var(--font-weight-medium); color:var(--text-primary); }.gdex__hint,.gdex__text,.gdex__sub { display:block; margin-top:4px; font-size:var(--font-size-xs); line-height:1.55; color:var(--text-secondary); word-break:break-word; }.gdex__refresh,.gdex__status { flex:none; font-size:var(--font-size-xs); color:var(--primary-600); }.gdex__status.muted { color:var(--text-tertiary); }
.gdex__summary { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:var(--space-2); margin-top:var(--space-3); }.gdex__summary > view { min-width:0; padding:var(--space-2); border-radius:var(--radius-md); background:var(--primary-50); color:var(--text-tertiary); font-size:var(--font-size-xs); }.gdex__summary-wide { grid-column:1 / -1; }.gdex__summary-value { display:block; margin-top:4px; color:var(--text-primary); font-weight:var(--font-weight-medium); word-break:break-word; }
.gdex__state { margin-top:var(--space-3); padding:var(--space-3); border-radius:var(--radius-md); background:var(--gray-50); color:var(--text-secondary); font-size:var(--font-size-sm); }.gdex__state--error { border:1px solid var(--danger-100); background:var(--danger-50); }.gdex__error { display:block; color:var(--danger-600); line-height:1.5; }.gdex__retry { margin-top:var(--space-2); min-height:36px; line-height:36px; font-size:var(--font-size-sm); }
.gdex__card { margin-top:var(--space-3); padding:var(--space-3); border:1px solid var(--border-light); border-radius:var(--radius-md); background:var(--gray-50); overflow:hidden; }.gdex__card--action { border-color:var(--primary-200); background:var(--primary-50); }.gdex__timeline { margin-top:var(--space-2); padding-left:var(--space-2); border-left:2px solid var(--border-light); }.gdex__timeline text { display:block; margin-top:5px; color:var(--text-tertiary); font-size:var(--font-size-xs); line-height:1.5; word-break:break-word; }.gdex__timeline text.done { color:var(--success-600); }.gdex__ta { width:100%; min-height:82px; margin:var(--space-2) 0; padding:var(--space-2); box-sizing:border-box; border:1px solid var(--border-base); border-radius:var(--radius-md); background:var(--bg-card); }.gdex__ph { color:var(--text-tertiary); }.gdex__submit-row { display:flex; align-items:center; justify-content:space-between; gap:var(--space-2); color:var(--text-tertiary); font-size:var(--font-size-xs); }.gdex__submit { width:auto; margin:0; padding:0 var(--space-4); white-space:nowrap; }
</style>
