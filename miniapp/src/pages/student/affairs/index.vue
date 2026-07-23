<template>
  <view class="page-wrap">
    <view class="af__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="af__navbar"><text class="af__navbar-back" @click="back">‹</text><text class="af__navbar-title">学工中心</text></view>
      <view class="stat-strip" v-if="data">
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.leaveCount }}</text><text class="stat-strip__label">请假</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.aidApproved }}</text><text class="stat-strip__label">困难认定</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.fundingGranted }}</text><text class="stat-strip__label">获资助</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.riskOpen }}</text><text class="stat-strip__label">在办风险</text></view>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data" style="padding-top: var(--space-3);">
        <view class="card">
          <view class="icon-grid">
            <view v-for="(it, i) in entries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
            </view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">我的处分</text></view>
        <view class="card" @click="go('/pages/student/affairs/discipline')">
          <text class="t-sm t-secondary">{{ discNote }}</text>
          <text class="t-sm link">进入申诉 ›</text>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7']
const ENTRIES = [
  { key: 'leave', label: '我的请假', icon: '📝', route: '/pages/student/affairs/leave' },
  { key: 'dorm', label: '我的宿舍', icon: '🏠', route: '/pages/student/affairs/dorm' },
  { key: 'aid', label: '困难认定', icon: '🤝', route: '/pages/student/affairs/aid' },
  { key: 'funding', label: '奖助申请', icon: '💰', route: '/pages/student/affairs/funding' },
  { key: 'discipline', label: '违纪申诉', icon: '⚖️', route: '/pages/student/affairs/discipline' },
  { key: 'talk', label: '谈心谈话', icon: '💬', route: '/pages/student/affairs/talk' },
  { key: 'activity', label: '活动与二课', icon: '🎉', route: '/pages/student/affairs/activity' },
  { key: 'service', label: '在校服务', icon: '🏫', route: '/pages/student/campus-service/index' }
]

export default {
  data() { return { data: null, disc: null, state: 'loading', statusBarHeight: 20, entries: ENTRIES } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  computed: {
    discNote() {
      if (!this.disc) return '生效中处分数量'
      return this.disc.activeCount > 0 ? `生效中 ${this.disc.activeCount} 条（${this.disc.detailNote || '明细请联系辅导员'}）` : '暂无生效处分'
    }
  },
  methods: {
    go,
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getAffairsOverview(), studentApi.getMyDiscipline().catch(() => null)])
        .then(([ov, d]) => { this.data = ov; this.disc = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.af__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.af__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.af__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.af__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.link { display: block; margin-top: 8px; color: #2563eb; }
</style>
