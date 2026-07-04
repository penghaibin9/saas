<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <template v-if="i && !i.hasBatch">
        <view class="page-pad"><MobileGlobalState state="empty" title="当前暂无实习任务" description="进入实习阶段后，这里会显示岗位、协议、打卡与周报。" /></view>
      </template>
      <view class="page-pad stack" v-else-if="i">
        <!-- 实习概览 -->
        <view class="in__hero card">
          <text class="in__hero-batch">{{ i.batch }}</text>
          <text class="in__hero-post">{{ i.post }}</text>
          <text class="in__hero-company">{{ i.company }}</text>
          <view class="in__hero-mentors">
            <text class="in__mentor">校内导师 {{ i.schoolMentor }}</text>
            <text class="in__mentor">企业导师 {{ i.companyMentor }}</text>
          </view>
        </view>

        <!-- 今日两大主任务：打卡 + 周报 -->
        <view class="in__today">
          <view class="in__today-card" @click="checkin">
            <text class="in__today-icon">📍</text>
            <text class="in__today-title">今日打卡</text>
            <text class="in__today-status" :class="{ 'is-warn': !i.checkin.done }">{{ i.checkin.done ? '已打卡' : '未打卡' }}</text>
            <text class="in__today-btn">{{ i.checkin.done ? '已完成' : '去打卡' }}</text>
          </view>
          <view class="in__today-card" @click="weekly">
            <text class="in__today-icon">✎</text>
            <text class="in__today-title">{{ i.weekly.week }}周报</text>
            <text class="in__today-status" :class="{ 'is-warn': !i.weekly.submitted }">{{ i.weekly.submitted ? '已提交' : '未提交' }}</text>
            <text class="in__today-btn">写周报</text>
          </view>
        </view>
        <MobileInlineAlert type="info" :description="i.checkin.note" />

        <!-- 上周反馈 -->
        <MobileInlineAlert v-if="i.weekly.lastFeedback" type="warning" title="导师上周反馈" :description="i.weekly.lastFeedback" />

        <!-- 状态清单 -->
        <view class="section-head"><text class="section-head__title">实习状态</text></view>
        <view class="card">
          <view class="in__status-grid">
            <view class="in__status-item"><text class="in__status-k">协议</text><MobileStatusTag :status="i.status.agreement" /></view>
            <view class="in__status-item"><text class="in__status-k">保险</text><MobileStatusTag :status="i.status.insurance" /></view>
            <view class="in__status-item"><text class="in__status-k">到岗</text><MobileStatusTag :status="i.status.onboard" /></view>
            <view class="in__status-item"><text class="in__status-k">今日打卡</text><MobileStatusTag :status="i.status.todayCheckin" /></view>
            <view class="in__status-item"><text class="in__status-k">本周周报</text><MobileStatusTag :status="i.status.weekly" /></view>
            <view class="in__status-item"><text class="in__status-k">请假</text><MobileStatusTag :status="i.status.leave" /></view>
          </view>
        </view>

        <!-- 实习流程 -->
        <view class="section-head"><text class="section-head__title">实习流程</text></view>
        <view class="card"><MobileTimeline :nodes="i.timeline" /></view>

        <!-- 功能入口 -->
        <view class="section-head"><text class="section-head__title">实习功能</text></view>
        <view class="in__entries card">
          <text v-for="e in i.entries" :key="e" class="in__entry" @click="toast(e + '（演示）')">{{ e }}</text>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="i && i.hasBatch">
      <button class="btn btn-ghost flex-1" @click="weekly">写周报</button>
      <button class="btn btn-primary flex-1" @click="checkin">{{ i.checkin.done ? '已打卡' : '一键打卡' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { useSubmissionsStore } from '@/stores/submissions'
import { toast, go } from '@/utils/nav'
export default {
  data() { return { i: null, state: 'loading' } },
  onLoad() { this.load() },
  onShow() {
    if (this.i && useSubmissionsStore().hasWeekly(this.i.weekly.week)) {
      this.i.weekly.submitted = true
      this.i.status.weekly = 'COMPLETED'
    }
  },
  methods: {
    toast,
    load() {
      this.state = 'loading'
      studentApi.getInternship().then((d) => { this.i = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    checkin() {
      if (this.i.checkin.done) return toast('今日已打卡')
      uni.showModal({ title: '实习打卡', content: '仅在此刻采集定位，不后台持续定位。确认打卡？', success: (r) => {
        if (r.confirm) { this.i.checkin.done = true; this.i.status.todayCheckin = 'COMPLETED'; toast('打卡成功（演示）') }
      } })
    },
    weekly() {
      if (this.i.weekly.submitted || useSubmissionsStore().hasWeekly(this.i.weekly.week)) {
        this.i.weekly.submitted = true
        this.i.status.weekly = 'COMPLETED'
        return toast('本周周报已提交')
      }
      const q = 'week=' + encodeURIComponent(this.i.weekly.week) +
        '&company=' + encodeURIComponent(this.i.company) +
        '&post=' + encodeURIComponent(this.i.post)
      go('/pages/student/weekly-report/index?' + q)
    }
  }
}
</script>

<style scoped>
.in__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.in__hero-post { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin-top: 4px; }
.in__hero-company { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-top: 2px; }
.in__hero-mentors { display: flex; gap: var(--space-3); margin-top: var(--space-3); }
.in__mentor { font-size: var(--font-size-xs); color: var(--text-secondary); background: var(--gray-100); padding: 3px 8px; border-radius: var(--radius-full); }
.in__today { display: flex; gap: var(--card-gap-mobile); }
.in__today-card { flex: 1; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--card-padding-mobile); box-shadow: var(--shadow-card); display: flex; flex-direction: column; gap: 4px; }
.in__today-icon { font-size: 24px; }
.in__today-title { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.in__today-status { font-size: var(--font-size-sm); color: var(--success-600); }
.in__today-status.is-warn { color: var(--warning-600); }
.in__today-btn { margin-top: var(--space-2); font-size: var(--font-size-sm); color: var(--brand-primary); }
.in__status-grid { display: flex; flex-wrap: wrap; }
.in__status-item { width: 33.33%; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: var(--space-2) 0; }
.in__status-k { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.in__entries { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.in__entry { font-size: var(--font-size-sm); color: var(--text-secondary); background: var(--gray-50); border: 1px solid var(--border-base); padding: 7px 12px; border-radius: var(--radius-md); }
</style>
