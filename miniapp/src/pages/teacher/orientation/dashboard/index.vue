<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="迎新看板" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="card od__batch">
          <text class="t-md t-bold">{{ d.batchName || '迎新批次' }}</text>
          <text v-if="d.batchPeriod" class="od__batch-period">{{ d.batchPeriod }}</text>
        </view>

        <view class="od__kpis">
          <view v-for="k in d.kpis" :key="k.key" class="od__kpi card">
            <text class="od__kpi-val">{{ k.value }}</text>
            <text class="od__kpi-label">{{ k.label }}</text>
            <text v-if="k.trend" class="od__kpi-trend" :class="'is-' + k.trendQuality">{{ k.trend }}</text>
          </view>
        </view>

        <view class="card od__entry" @click="goGc">
          <view class="flex-1">
            <text class="t-md t-bold">绿色通道审核</text>
            <text class="od__entry-sub">审核学生缓缴 / 减免申请，通过后自动解除缴费卡点</text>
          </view>
          <text class="od__entry-arrow">›</text>
        </view>

        <view class="section-head">
          <text class="section-head__title">未报到新生</text>
          <text class="section-head__more">{{ d.notReportedTotal }} 人</text>
        </view>
        <MobileGlobalState v-if="!d.notReported.length" state="empty" title="新生均已报到" description="当前没有未报到的新生记录。" />
        <view v-else class="card stack-sm">
          <view v-for="s in d.notReported" :key="s.id" class="od__row">
            <view class="od__row-avatar">{{ s.name.slice(0,1) }}</view>
            <view class="flex-1">
              <text class="t-md">{{ s.name }}</text>
              <text class="od__row-sub">{{ s.className || '待分班' }} · 进度 {{ s.progress }}</text>
            </view>
            <text v-if="s.blockedReason" class="od__row-blocked">{{ s.blockedReason }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
export default {
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    goGc() { uni.navigateTo({ url: '/pages/teacher/orientation/green-channel/index' }) },
    load() {
      this.state = 'loading'
      teacherApi.getOrientationDashboard().then((data) => {
        if (!data || !data.hasData) { this.state = 'empty'; return }
        this.d = data
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.od__batch { display: flex; align-items: baseline; gap: var(--space-2); }
.od__batch-period { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.od__kpis { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--card-gap-mobile); margin-top: var(--card-gap-mobile); }
.od__kpi { display: flex; flex-direction: column; gap: 4px; }
.od__kpi-val { font-size: var(--font-size-metric); font-weight: var(--font-weight-semibold); color: var(--teacher-700); }
.od__kpi-label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.od__kpi-trend { font-size: var(--font-size-xs); }
.od__kpi-trend.is-good { color: var(--success-600); }
.od__kpi-trend.is-bad { color: var(--danger-600); }
.od__kpi-trend.is-neutral { color: var(--text-tertiary); }
.od__row { display: flex; align-items: center; gap: var(--space-3); }
.od__row-avatar { width: 36px; height: 36px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.od__row-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.od__row-blocked { font-size: var(--font-size-xs); color: var(--danger-600); background: var(--danger-50); padding: 3px 8px; border-radius: var(--radius-base); }
.od__entry { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--card-gap-mobile); }
.od__entry-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.od__entry-arrow { font-size: 20px; color: var(--text-tertiary); }
</style>
