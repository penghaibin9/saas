<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="消息详情" show-back />
    <view class="page-pad stack" v-if="m">
      <view class="card">
        <view class="row-between">
          <text class="md__module">{{ m.module || '消息' }}</text>
          <text v-if="m.level === 'high'" class="md__urgent">重要</text>
        </view>
        <text class="md__title">{{ m.title }}</text>
        <text class="md__time">{{ formatTime(m.time) }}</text>
        <view v-if="m.status" style="margin-top: var(--space-2);"><MobileStatusTag :status="m.status" /></view>
        <text v-if="m.content" class="md__content">{{ m.content }}</text>
        <text v-if="m.deadline" class="md__deadline">截止时间：{{ formatTime(m.deadline) }}</text>
      </view>
    </view>
    <MobileGlobalState v-else state="empty" title="消息不存在或已过期" description="请返回消息列表重新查看。" />

    <MobileSafeAreaBar v-if="m && (m.actionable || m.receipt)">
      <button v-if="m.actionable" class="btn btn-primary flex-1" @click="handle">去处理</button>
      <button v-if="m.receipt" class="btn btn-ghost flex-1" @click="ackToast">确认回执</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { popDetail } from '@/utils/msgStash'
import { go, toast } from '@/utils/nav'

export default {
  data() { return { m: null } },
  onLoad() { this.m = popDetail() },
  methods: {
    formatTime(t) { return t ? String(t).slice(0, 16).replace('T', ' ') : '' },
    ackToast() { toast('回执确认功能即将开放') },
    handle() {
      if (!this.m) return
      if (this.m.status === 'RETURNED') return go('/pages/student/my-applications/index')
      const mod = this.m.module || ''
      if (mod.indexOf('实习') >= 0) return go('/pages/teacher/internship-review/index')
      if (mod.indexOf('风险') >= 0 || mod.indexOf('预警') >= 0) return go('/pages/teacher/risk-students/index')
      if (mod.indexOf('毕业') >= 0) return go('/pages/teacher/graduation-guide/index')
      go('/pages/student/campus-service/index')
    }
  }
}
</script>

<style scoped>
.md__module { font-size: var(--font-size-sm); color: var(--brand-primary); }
.md__urgent { font-size: 11px; color: #fff; background: var(--danger-500); padding: 2px 8px; border-radius: var(--radius-sm); }
.md__title { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin-top: var(--space-2); line-height: 1.5; }
.md__time { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.md__content { display: block; font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.7; margin-top: var(--space-4); white-space: pre-wrap; }
.md__deadline { display: block; font-size: var(--font-size-sm); color: var(--warning-700); margin-top: var(--space-3); }
</style>
