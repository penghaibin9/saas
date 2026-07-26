<template>
  <view v-if="visible" class="gdex">
    <view class="gdex__head">
      <view><text class="gdex__title">延期答辩与优秀成果</text><text class="gdex__hint">延期按四级闭环审批；成绩优秀不等于优秀成果已认定。</text></view>
      <text class="gdex__refresh" @click="load">刷新</text>
    </view>
    <text v-if="error" class="gdex__error">{{ error }}</text>
    <template v-else-if="data">
      <view v-if="data.defenseDelay" class="gdex__card">
        <view class="row-between"><text class="t-md t-bold">延期答辩</text><text class="gdex__status">{{ data.defenseDelay.statusLabel }}</text></view>
        <text class="gdex__text">理由：{{ data.defenseDelay.reason }}</text>
        <text v-if="data.defenseDelay.advisorComment" class="gdex__text">导师：{{ data.defenseDelay.advisorComment }}</text>
        <text v-if="data.defenseDelay.majorComment" class="gdex__text">专业：{{ data.defenseDelay.majorComment }}</text>
        <text v-if="data.defenseDelay.collegeComment" class="gdex__text">学院：{{ data.defenseDelay.collegeComment }}</text>
        <text v-if="data.defenseDelay.plannedDefenseDate" class="gdex__text">排期：{{ data.defenseDelay.plannedDefenseDate }} · {{ data.defenseDelay.defenseGroupName || '答辩组待发布' }}</text>
      </view>
      <view v-else-if="data.canApplyDelay" class="gdex__card">
        <view class="row-between"><text class="t-md t-bold">申请延期答辩</text><text class="gdex__status">可申请</text></view>
        <textarea v-model="reason" class="gdex__ta" maxlength="1000" placeholder="说明延期原因、当前情况和预计准备时间（至少10字）" placeholder-class="gdex__ph" />
        <button class="btn btn-primary" :disabled="submitting || reason.trim().length < 10" @click="apply">提交延期申请</button>
      </view>
      <view v-else class="gdex__card"><view class="row-between"><text class="t-md t-bold">延期答辩</text><text class="gdex__status muted">当前不可申请</text></view><text class="gdex__text">仅成果检查/答辩阶段且成绩未发布时可申请。</text></view>

      <view v-if="data.excellentOutcome" class="gdex__card">
        <view class="row-between"><text class="t-md t-bold">优秀成果认定</text><text class="gdex__status">{{ data.excellentOutcome.statusLabel }}</text></view>
        <text class="gdex__text">提名理由：{{ data.excellentOutcome.nominationReason }}</text>
        <text v-if="data.excellentOutcome.majorReviewComment" class="gdex__text">专业：{{ data.excellentOutcome.majorReviewComment }}</text>
        <text v-if="data.excellentOutcome.collegeReviewComment" class="gdex__text">学院：{{ data.excellentOutcome.collegeReviewComment }}</text>
      </view>
      <view v-else class="gdex__card"><view class="row-between"><text class="t-md t-bold">优秀成果认定</text><text class="gdex__status muted">暂无记录</text></view><text class="gdex__text">导师提名后，须经过专业复核和学院终审。</text></view>
    </template>
  </view>
</template>

<script>
import { realRequest, normalizeError } from '@/services/request'
function pageStack() { return typeof getCurrentPages === 'function' ? getCurrentPages() : [] }
let owner = null
export default {
  name: 'MobileGraduationExtensionPanel',
  data() { return { visible: false, data: null, error: '', reason: '', submitting: false, owns: false } },
  mounted() {
    const pages = pageStack(); const page = pages[pages.length - 1]
    const match = ((page && (page.route || page.__route__)) || '') === 'pages/student/graduation/index'
    if (match && owner == null) { owner = this._uid; this.owns = true; this.visible = true; this.load() }
  },
  beforeUnmount() { if (this.owns && owner === this._uid) owner = null },
  methods: {
    load() {
      this.error = ''
      realRequest('/mobile/graduation/extensions/my').then((d) => { this.data = d })
        .catch((e) => { this.error = normalizeError(e).text || '扩展事项加载失败' })
    },
    apply() {
      const reason = this.reason.trim()
      if (reason.length < 10 || this.submitting) return
      this.submitting = true
      realRequest('/mobile/graduation/defense-delay/apply', { method: 'POST', data: { reason } })
        .then(() => { this.reason = ''; uni.showToast({ title: '申请已提交', icon: 'success' }); this.load() })
        .catch((e) => { this.error = normalizeError(e).text || '延期申请提交失败' })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.gdex { margin:0 var(--page-padding-mobile) var(--space-3); padding:var(--space-3); border:1px solid var(--border-light); border-radius:var(--radius-lg); background:var(--bg-card); }
.gdex__head { display:flex; justify-content:space-between; gap:var(--space-2); }.gdex__title { display:block; font-size:var(--font-size-base); font-weight:var(--font-weight-medium); color:var(--text-primary); }.gdex__hint,.gdex__text { display:block; margin-top:4px; font-size:var(--font-size-xs); line-height:1.5; color:var(--text-secondary); }.gdex__refresh,.gdex__status { flex:none; font-size:var(--font-size-xs); color:var(--primary-600); }.gdex__status.muted { color:var(--text-tertiary); }.gdex__card { margin-top:var(--space-3); padding:var(--space-3); border:1px solid var(--border-light); border-radius:var(--radius-md); background:var(--gray-50); }.gdex__ta { width:100%; min-height:76px; margin:var(--space-2) 0; padding:var(--space-2); box-sizing:border-box; border:1px solid var(--border-base); border-radius:var(--radius-md); background:var(--bg-card); }.gdex__ph { color:var(--text-tertiary); }.gdex__error { display:block; margin-top:var(--space-2); color:var(--danger-600); font-size:var(--font-size-sm); }
</style>
