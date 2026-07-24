<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学分修读" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <view class="cr__metrics">
            <view class="cr__metric">
              <text class="cr__metric-val">{{ d.obtainedCredits }}<text class="cr__metric-unit">/{{ d.requiredCredits }}</text></text>
              <text class="cr__metric-label">已获/应修学分</text>
            </view>
            <view class="cr__metric">
              <text class="cr__metric-val">{{ d.gpa != null ? d.gpa : '—' }}</text>
              <text class="cr__metric-label">平均绩点</text>
            </view>
            <view class="cr__metric">
              <text class="cr__metric-val" :class="{ 't-danger': d.failCount > 0 }">{{ d.failCount }}</text>
              <text class="cr__metric-label">挂科门数</text>
            </view>
          </view>
          <view style="margin-top: var(--space-3);"><MobileProgress :value="pct" tone="success" /></view>
          <text class="cr__sub" style="margin-top:8px;display:block">本页为学分汇总只读；培养方案分类占比以教务处发布口径为准。</text>
        </view>

        <view class="section-head"><text class="section-head__title">已通过课程（{{ d.passedCourses.length }}）</text></view>
        <view class="list-group" v-if="d.passedCourses.length">
          <view v-for="(c, i) in d.passedCourses" :key="i" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ c.courseName }}</text>
              <text class="cr__sub">{{ c.term || '—' }} · {{ c.credit }} 学分</text>
            </view>
            <text class="cr__score">{{ c.score != null ? c.score : '—' }}</text>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无已通过课程" description="成绩发布后会显示在这里。" />

        <view class="cr__note"><text class="t-xs t-tertiary">说明：本页仅展示真实学分汇总与已通过课程，不提供公共课/专业课等类别拆分（当前数据模型未采集分类信息）。</text></view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { clampPercent } from '@/utils/format'

export default {
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  computed: {
    pct() {
      if (!this.d || !this.d.requiredCredits) return 0
      return clampPercent((this.d.obtainedCredits / this.d.requiredCredits) * 100)
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyCredits().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.cr__metrics { display: flex; }
.cr__metric { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.cr__metric-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--brand-primary); }
.cr__metric-unit { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.cr__metric-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.cr__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.cr__score { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--success-600); }
.cr__note { margin-top: var(--space-2); }
.t-danger { color: var(--danger-600) !important; }
</style>
