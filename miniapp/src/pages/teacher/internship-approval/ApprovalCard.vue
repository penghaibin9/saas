<template>
  <view class="card item-card">
    <view class="row-between">
      <view class="flex-1">
        <text class="title">{{ item.studentName || '—' }}</text>
        <text class="sub">{{ item.studentNo || '' }} · {{ kindLabel }}</text>
      </view>
      <MobileStatusTag :label="item.statusLabel || '待审核'" type="warning" />
    </view>

    <view class="detail">
      <text class="key">{{ kind === 'makeup' ? '补卡日期' : '请假起止' }}</text>
      <text class="flex-1">{{ rangeText }}</text>
    </view>
    <view class="detail"><text class="key">申请事由</text><text class="flex-1 content">{{ item.reason || '—' }}</text></view>
    <view class="detail"><text class="key">提交时间</text><text>{{ formatTime(item.submittedAt || item.createdAt) }}</text></view>

    <view v-if="item.previousReviewComment" class="history-box">
      <text class="history-title">历史退回意见</text>
      <text class="history-content">{{ item.previousReviewComment }}</text>
      <text v-if="item.previousReviewAt" class="history-time">{{ formatTime(item.previousReviewAt) }}</text>
    </view>

    <view class="evidence-box" :class="{ required: evidenceRequired, missing: evidenceRequired && !hasEvidence }">
      <view class="row-between">
        <view class="flex-1">
          <text class="evidence-title">证明材料 {{ evidenceRequired ? '· 必需' : '· 选传' }}</text>
          <text class="evidence-hint">{{ item.evidenceRequirementLabel || defaultEvidenceHint }}</text>
        </view>
        <MobileStatusTag
          :label="hasEvidence ? (evidenceViewed ? '已查看' : '待查看') : '未上传'"
          :type="hasEvidence ? (evidenceViewed ? 'success' : 'warning') : (evidenceRequired ? 'danger' : 'default')"
        />
      </view>
      <button
        v-if="hasEvidence"
        class="evidence-button"
        :disabled="viewing || acting"
        @click="$emit('view-evidence', { kind, item })"
      >{{ viewing ? '正在打开…' : (evidenceViewed ? '再次查看材料' : '查看材料并留痕') }}</button>
      <text v-else-if="evidenceRequired" class="block-reason">缺少规则要求的材料，后端将拒绝通过。</text>
    </view>

    <view class="detail"><text class="key">数据版本</text><text>v{{ item.version }}</text></view>
    <view v-if="!canReview" class="permission-tip">当前身份仅有查看权限，没有该类审批权限。</view>
    <view v-else-if="hasEvidence && !evidenceViewed" class="permission-tip warning">必须先真实打开材料并写入查看留痕，才能通过。</view>

    <view class="actions">
      <button
        class="reject flex-1"
        :disabled="acting || viewing || !canReview"
        @click="$emit('review', { kind, item, action: 'REJECT' })"
      >驳回</button>
      <button
        class="approve flex-1"
        :disabled="acting || viewing || !canReview || approveBlocked"
        @click="$emit('review', { kind, item, action: 'APPROVE' })"
      >{{ approveText }}</button>
    </view>
  </view>
</template>

<script>
export default {
  props: {
    item: { type: Object, required: true },
    kind: { type: String, required: true },
    acting: { type: Boolean, default: false },
    viewing: { type: Boolean, default: false },
    canReview: { type: Boolean, default: false },
    evidenceViewed: { type: Boolean, default: false }
  },
  emits: ['review', 'view-evidence'],
  computed: {
    kindLabel() {
      if (this.kind === 'makeup') return this.item.makeupTypeLabel || this.item.makeupType || '补卡'
      return `${this.item.leaveTypeLabel || this.item.leaveType || '请假'} · ${this.item.days || 0}天`
    },
    rangeText() {
      return this.kind === 'makeup'
        ? (this.item.checkinDate || '—')
        : `${this.item.startDate || '—'} ~ ${this.item.endDate || '—'}`
    },
    hasEvidence() { return !!this.item.evidenceFileId },
    evidenceRequired() { return this.item.evidenceRequired === true },
    approveBlocked() {
      return (this.evidenceRequired && !this.hasEvidence) || (this.hasEvidence && !this.evidenceViewed)
    },
    approveText() {
      if (this.acting) return '处理中…'
      if (!this.canReview) return '无审批权限'
      if (this.evidenceRequired && !this.hasEvidence) return '缺少必需材料'
      if (this.hasEvidence && !this.evidenceViewed) return '请先查看材料'
      return this.kind === 'makeup' ? '通过并补写打卡' : '通过并写请假留痕'
    },
    defaultEvidenceHint() {
      return this.kind === 'makeup' ? '可上传考勤、定位或现场佐证' : '可上传医疗、单位或其他请假证明'
    }
  },
  methods: {
    formatTime(value) {
      if (!value) return '—'
      return String(value).replace('T', ' ').slice(0, 16)
    }
  }
}
</script>

<style scoped>
.item-card{display:flex;flex-direction:column;gap:14rpx}.title{font-size:30rpx;font-weight:600}.sub{display:block;margin-top:4rpx;color:var(--text-tertiary);font-size:24rpx}.detail{display:flex;gap:20rpx;font-size:26rpx}.key{width:130rpx;color:var(--text-tertiary);flex-shrink:0}.content{line-height:1.55}.history-box{padding:18rpx 20rpx;border-radius:14rpx;background:var(--warning-50,#fff7ed);border:1px solid var(--warning-200,#fed7aa)}.history-title{display:block;color:var(--warning-800,#9a3412);font-size:24rpx;font-weight:600}.history-content{display:block;margin-top:6rpx;color:var(--text-primary);font-size:25rpx;line-height:1.5}.history-time{display:block;margin-top:6rpx;color:var(--text-tertiary);font-size:22rpx}.evidence-box{padding:18rpx 20rpx;border-radius:14rpx;background:var(--gray-50);border:1px solid var(--border-base)}.evidence-box.required{border-color:var(--warning-300,#fdba74)}.evidence-box.missing{background:var(--danger-50,#fef2f2);border-color:var(--danger-300,#fca5a5)}.evidence-title{display:block;font-size:25rpx;font-weight:600}.evidence-hint{display:block;margin-top:5rpx;color:var(--text-tertiary);font-size:22rpx;line-height:1.45}.evidence-button{margin-top:14rpx;min-height:72rpx;border:1px solid var(--teacher-500);background:var(--bg-card);color:var(--teacher-700);border-radius:12rpx;font-size:25rpx}.evidence-button::after{border:0}.block-reason{display:block;margin-top:10rpx;color:var(--danger-600);font-size:23rpx}.permission-tip{padding:14rpx 18rpx;border-radius:12rpx;background:var(--gray-100);color:var(--text-secondary);font-size:23rpx}.permission-tip.warning{background:var(--warning-50,#fff7ed);color:var(--warning-800,#9a3412)}.actions{display:flex;gap:16rpx;margin-top:4rpx}.reject,.approve{min-height:88rpx;border-radius:16rpx;font-size:28rpx}.reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.approve{border:0;background:var(--teacher-600);color:#fff}.reject::after,.approve::after{border:0}.reject[disabled],.approve[disabled],.evidence-button[disabled]{opacity:.55}
</style>
