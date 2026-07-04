<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="a">
        <!-- 学业总览 -->
        <view class="ac__overview card">
          <view class="ac__metric">
            <text class="ac__metric-val">{{ a.summary.gpa }}</text>
            <text class="ac__metric-label">平均绩点</text>
          </view>
          <view class="ac__metric">
            <text class="ac__metric-val">{{ a.summary.rank }}</text>
            <text class="ac__metric-label">专业排名</text>
          </view>
          <view class="ac__metric">
            <text class="ac__metric-val">{{ a.summary.creditEarned }}<text class="ac__metric-unit">/{{ a.summary.creditTotal }}</text></text>
            <text class="ac__metric-label">已修学分</text>
          </view>
        </view>
        <view class="card">
          <view class="row-between"><text class="t-sm t-secondary">毕业学分进度</text><text class="t-sm t-secondary">{{ creditPct }}%</text></view>
          <view style="margin-top:8px;"><MobileProgress :value="creditPct" tone="success" :show-text="false" /></view>
        </view>

        <template v-if="a.warnings.length">
          <MobileInlineAlert type="danger" title="学业预警" :description="a.warnings.join('；')" />
        </template>

        <!-- 学期进度 -->
        <view class="section-head"><text class="section-head__title">学期进度</text></view>
        <view class="card stack-sm">
          <view v-for="t in a.termProgress" :key="t.term" class="ac__term">
            <view class="flex-1">
              <text class="t-md">{{ t.term }}</text>
              <text class="ac__term-sub">绩点 {{ t.gpa }} · {{ t.credit }} 学分</text>
            </view>
            <MobileStatusTag :status="t.status" />
          </view>
        </view>

        <!-- 本学期课程 -->
        <view class="section-head"><text class="section-head__title">课程与成绩</text></view>
        <view class="stack-sm">
          <view v-for="c in a.courses" :key="c.id" class="ac__course card">
            <view class="row-between">
              <text class="t-md t-bold">{{ c.name }}</text>
              <text v-if="c.score !== null" class="ac__score">{{ c.score }}</text>
              <MobileStatusTag v-else :status="c.status" />
            </view>
            <text class="ac__course-teacher">{{ c.teacher }} · {{ c.credit }} 学分</text>
            <view v-if="c.status === 'PROCESSING'" style="margin-top:8px;">
              <MobileProgress :value="c.progress" tone="brand" />
            </view>
          </view>
        </view>

        <!-- 考试安排 -->
        <view class="section-head"><text class="section-head__title">考试安排</text></view>
        <view class="card stack-sm">
          <view v-for="e in a.exams" :key="e.id" class="ac__exam">
            <view class="ac__exam-icon">📝</view>
            <view class="flex-1">
              <text class="t-md">{{ e.name }}</text>
              <text class="ac__exam-info">{{ e.time }} · {{ e.place }} · {{ e.seat }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { clampPercent } from '@/utils/format'
export default {
  data() { return { a: null, state: 'loading' } },
  onLoad() { this.load() },
  computed: {
    creditPct() {
      if (!this.a) return 0
      return clampPercent((this.a.summary.creditEarned / this.a.summary.creditTotal) * 100)
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getAcademic().then((d) => { this.a = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.ac__overview { display: flex; }
.ac__metric { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.ac__metric-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--brand-primary); }
.ac__metric-unit { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.ac__metric-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ac__term { display: flex; align-items: center; }
.ac__term-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ac__course-teacher { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; }
.ac__score { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--success-600); }
.ac__exam { display: flex; align-items: center; gap: var(--space-3); }
.ac__exam-icon { font-size: 22px; }
.ac__exam-info { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
</style>
