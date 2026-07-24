<template>
  <view class="page-wrap">
    <view class="ta__hero hero-band is-teacher">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="ta__navbar"><text class="ta__navbar-back" @click="back">‹</text><text class="ta__navbar-title">教务中心</text></view>
    </view>

    <view class="page-pad" style="padding-top: var(--space-3);">
      <view class="card">
        <view class="icon-grid">
          <view v-for="(it, i) in entries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
            <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
            <text class="icon-grid__label">{{ it.label }}</text>
          </view>
        </view>
      </view>
    </view>
    <MobileTabBar side="teacher" active="home" />
  </view>
</template>

<script>
import { go } from '@/utils/nav'

const GRAD_CLASSES = ['g1', 'g4', 'g3']
const ENTRIES = [
  { key: 'schedule', label: '我的课表', icon: '📅', route: '/pages/teacher/my-schedule/index' },
  { key: 'grade-entry', label: '成绩录入', icon: '📊', route: '/pages/teacher/academic-affairs/grade-entry' },
  { key: 'attendance', label: '课堂考勤', icon: '✅', route: '/pages/teacher/academic-affairs/attendance' },
  { key: 'schedule-change', label: '调停课', icon: '🔀', route: '/pages/teacher/schedule-change/index' },
  { key: 'sc-review', label: '调停课审批', icon: '✔️', route: '/pages/teacher/academic-affairs/schedule-change-review' },
  { key: 'st-review', label: '异动审批', icon: '📋', route: '/pages/teacher/academic-affairs/status-change-review' },
  { key: 'exam-defer', label: '缓考审批', icon: '📝', route: '/pages/teacher/exam-defer/index' },
  { key: 'academic-task', label: '教学任务', icon: '📚', route: '/pages/teacher/academic-task/index' },
  { key: 'evaluation', label: '教学评价', icon: '⭐', route: '/pages/teacher/evaluation/index' },
  { key: 'workload', label: '工作量申报', icon: '🧾', route: '/pages/teacher/academic-affairs/workload' },
  { key: 'warning', label: '学业预警', icon: '⚠', route: '/pages/teacher/academic-warning/index' }
]

export default {
  data() { return { statusBarHeight: 20, entries: ENTRIES } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
  },
  methods: {
    go,
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/teacher/workbench/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] }
  }
}
</script>

<style scoped>
.ta__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.ta__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.ta__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.ta__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
</style>
