<template>
  <view class="page-wrap">
    <view class="aa__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="aa__navbar"><text class="aa__navbar-back" @click="back">‹</text><text class="aa__navbar-title">教务中心</text></view>
      <view class="aa__status" v-if="status">
        <text class="aa__status-t">学籍状态</text>
        <text class="aa__status-v">{{ statusText(status.studentStatus) }}</text>
        <text class="aa__status-tag" :class="{ 'is-warn': !status.enrolled }">{{ status.enrolled ? '在籍' : '非在籍' }}</text>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="status" style="padding-top: var(--space-3);">
        <view class="card">
          <view class="icon-grid">
            <view v-for="(it, i) in entries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

const ST = { REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', RETAINED: '留级',
  WITHDRAWN: '已退学', GRADUATED: '已毕业', COMPLETED: '已结业', PENDING_REGISTER: '待注册' }
const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']
const ENTRIES = [
  { key: 'schedule', label: '我的课表', icon: '📅', route: '/pages/student/academic-affairs/schedule' },
  { key: 'transcript', label: '我的成绩', icon: '📊', route: '/pages/student/academic-affairs/transcript' },
  { key: 'credits', label: '学分修读', icon: '🎯', route: '/pages/student/academic-affairs/credits' },
  { key: 'warning', label: '学业预警', icon: '⚠', route: '/pages/student/academic-affairs/warning' },
  { key: 'makeup', label: '补考重修', icon: '📝', route: '/pages/student/academic-affairs/makeup' },
  { key: 'selection', label: '网上选课', icon: '✅', route: '/pages/student/academic-affairs/selection' },
  { key: 'status', label: '学籍与异动', icon: '📋', route: '/pages/student/academic-affairs/status' },
  { key: 'graduation', label: '毕业进度', icon: '🎓', route: '/pages/student/academic-affairs/graduation' },
  { key: 'recognition', label: '成绩认定', icon: '🔄', route: '/pages/student/academic-affairs/recognition' },
  { key: 'recheck', label: '成绩复查', icon: '🔍', route: '/pages/student/academic-affairs/recheck' },
  { key: 'textbook', label: '我的教材', icon: '📚', route: '/pages/student/academic-affairs/textbook' },
  { key: 'levelExam', label: '等级考试', icon: '🏅', route: '/pages/student/academic-affairs/level-exam' },
  { key: 'majorSplit', label: '专业分流', icon: '🧭', route: '/pages/student/academic-affairs/major-split' }
]

export default {
  data() { return { status: null, state: 'loading', statusBarHeight: 20, entries: ENTRIES } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  methods: {
    go,
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    statusText(s) { return ST[s] || s },
    load() {
      this.state = 'loading'
      studentApi.getMyAcadStatus().then((d) => { this.status = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.aa__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.aa__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.aa__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.aa__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.aa__status { margin-top: var(--space-2); }
.aa__status-t { display: block; font-size: var(--font-size-sm); color: rgba(255,255,255,0.85); }
.aa__status-v { display: block; font-size: 20px; font-weight: 700; color: #fff; margin-top: 4px; }
.aa__status-tag { display: inline-block; margin-top: 6px; font-size: var(--font-size-xs); color: #fff; background: rgba(255,255,255,0.25); padding: 2px 10px; border-radius: var(--radius-full); }
.aa__status-tag.is-warn { background: rgba(217,119,6,0.85); }
</style>
