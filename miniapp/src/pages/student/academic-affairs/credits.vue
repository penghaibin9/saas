<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="学分修读" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <view class="cr__metrics">
            <view class="cr__metric">
              <text class="cr__metric-val">{{ d.obtainedCredits }}<text v-if="d.resolutionStatus === 'RESOLVED'" class="cr__metric-unit">/{{ d.requiredCredits }}</text></text>
              <text class="cr__metric-label">{{ d.resolutionStatus === 'RESOLVED' ? '已获/应修学分' : '已获学分' }}</text>
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
          <view v-if="d.resolutionStatus === 'RESOLVED'" style="margin-top: var(--space-3);"><MobileProgress :value="pct" tone="success" /></view>
          <view v-else class="cr__unresolved">
            <text class="t-sm">学校尚未完成你的培养方案绑定，暂时无法准确计算应修学分。</text>
            <text class="cr__sub">已获得成绩和学分不会丢失。</text>
          </view>
          <text class="cr__sub" style="margin-top:8px;display:block">本页为学分汇总只读；培养方案分类占比以教务处发布口径为准。</text>
        </view>

        <view class="section-head"><text class="section-head__title">已通过课程（{{ d.passedCourses.length }}）</text></view>
        <text class="cr__sub">{{ passedCoursesCoverageText }}</text>
        <view class="list-group" v-if="d.passedCourses.length">
          <view v-for="(c, i) in d.passedCourses.slice(0, listLimit)" :key="i" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ c.courseName }}</text>
              <text class="cr__sub">{{ c.term || '—' }} · {{ c.credit }} 学分</text>
            </view>
            <text class="cr__score">{{ c.score != null ? c.score : '—' }}</text>
          </view>
        </view>
        <button v-if="d.passedCourses.length > listLimit" class="btn" @click="listLimit += 20">查看更多课程</button>
        <AcademicPageState v-if="!d.passedCourses.length" state="empty" title="暂无已通过课程" description="成绩发布后会显示在这里。" />

        <button class="btn btn-primary" @click="go('/pages/student/academic-affairs/transcript')">查看正式成绩</button>
        <view class="cr__note"><text class="t-xs t-tertiary">学分分类以学校公布的培养方案为准。</text></view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { clampPercent } from '@/utils/format'
import { go } from '@/utils/nav'
import { academicReadPage } from './read-page'

export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', clearReadDataOnForbidden: true } },
  onLoad() { this.load() },
  computed: {
    pct() {
      if (!this.d || !this.d.requiredCredits) return 0
      return clampPercent((this.d.obtainedCredits / this.d.requiredCredits) * 100)
    },
    passedCoursesCoverageText() {
      const returned = (this.d && this.d.passedCourses || []).length
      const total = Number(this.d && this.d.passedCoursesTotal)
      return Number.isFinite(total) && total > returned
        ? `当前返回 ${returned}/${total} 门已通过课程；当前接口未提供翻页。`
        : `当前返回 ${returned} 门已通过课程；学校暂未提供总条数。`
    }
  },
  methods: {
    go,
    load() {
      return this.readAcademic(() => studentApi.getMyCredits(), (d) => {
        if (!Array.isArray(d.passedCourses)) throw new Error('学分信息无法核对')
        this.d = d
      })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.cr__metrics { display: flex; }
.cr__metric { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.cr__metric-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--brand-primary); }
.cr__metric-unit { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.cr__metric-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.cr__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.cr__score { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--success-600); }
.cr__note { margin-top: var(--space-2); }
.cr__unresolved { margin-top: var(--space-3); padding: 12px; border-radius: 10px; background: var(--warning-50); color: var(--text-primary); }
.t-danger { color: var(--danger-600) !important; }
</style>
