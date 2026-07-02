<template>
  <view class="mobile-student-card" @click="$emit('view')">
    <view class="msc-avatar">
      <text>{{ avatarText }}</text>
    </view>
    <view class="msc-body">
      <view class="msc-name-row">
        <text class="msc-name">{{ name }}</text>
        <MobileRiskTag v-if="riskLevel" :level="riskLevel" />
      </view>
      <text v-if="orgText" class="msc-org">{{ orgText }}</text>
      <view class="msc-meta">
        <text v-if="stage" class="msc-stage">{{ stage }}</text>
        <text v-if="currentTask" class="msc-task">{{ currentTask }}</text>
        <text v-if="pendingCount" class="msc-pending">待办 {{ pendingCount }}</text>
      </view>
      <text v-if="lastActivity" class="msc-activity">{{ lastActivity }}</text>
    </view>
    <view class="msc-actions" @click.stop>
      <slot name="actions" />
    </view>
  </view>
</template>

<script>
import MobileRiskTag from './MobileRiskTag.vue'

/**
 * MobileStudentCard 移动端学生卡片（教师端学生列表 / 学生360摘要）
 * Props: name、className、major、stage（当前阶段）、currentTask（当前任务）、
 *        riskLevel、pendingCount（未完成待办数）、lastActivity（最近动态）
 * Emits: view
 * Slots: actions（行内操作：查看摘要 / 联系 / 记录 / 处理）
 */
export default {
  name: 'MobileStudentCard',
  components: { MobileRiskTag },
  props: {
    name: { type: String, required: true },
    className: { type: String, default: '' },
    major: { type: String, default: '' },
    stage: { type: String, default: '' },
    currentTask: { type: String, default: '' },
    riskLevel: { type: String, default: '' },
    pendingCount: { type: Number, default: 0 },
    lastActivity: { type: String, default: '' }
  },
  emits: ['view'],
  computed: {
    avatarText() {
      return this.name ? this.name.slice(0, 1) : '生'
    },
    orgText() {
      return [this.major, this.className].filter(Boolean).join(' / ')
    }
  }
}
</script>

<style scoped>
.mobile-student-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--card-padding-mobile);
  box-shadow: var(--shadow-card);
}
.msc-avatar {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: var(--font-size-lg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.msc-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.msc-name-row { display: flex; align-items: center; gap: var(--space-2); }
.msc-name { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.msc-org { font-size: var(--font-size-sm); color: var(--text-secondary); }
.msc-meta { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.msc-stage { font-size: var(--font-size-sm); color: var(--primary-600); }
.msc-task { font-size: var(--font-size-sm); color: var(--text-secondary); }
.msc-pending { font-size: var(--font-size-sm); color: var(--warning-600); }
.msc-activity {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.msc-actions { flex-shrink: 0; display: flex; flex-direction: column; gap: var(--space-2); }
</style>
