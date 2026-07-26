<template>
  <view class="card item-card">
    <view class="row-between">
      <view class="flex-1">
        <text class="title">{{ item.studentName || '—' }}</text>
        <text class="sub">{{ item.studentNo || '' }} · {{ kind === 'makeup' ? (item.makeupTypeLabel || item.makeupType) : `${item.leaveTypeLabel || item.leaveType} · ${item.days || 0}天` }}</text>
      </view>
      <MobileStatusTag :label="item.statusLabel || '待审核'" type="warning" />
    </view>
    <view v-if="kind === 'makeup'" class="detail"><text class="key">补卡日期</text><text>{{ item.checkinDate || '—' }}</text></view>
    <view v-else class="detail"><text class="key">请假起止</text><text>{{ item.startDate || '—' }} ~ {{ item.endDate || '—' }}</text></view>
    <view class="detail"><text class="key">申请事由</text><text class="flex-1">{{ item.reason || '—' }}</text></view>
    <view v-if="kind === 'leave'" class="detail"><text class="key">证明材料</text><text>{{ item.fileId ? '已上传' : '未上传' }}</text></view>
    <view class="detail"><text class="key">数据版本</text><text>v{{ item.version }}</text></view>
    <view class="actions">
      <button class="reject flex-1" :disabled="acting" @click="$emit('review', { kind, item, action: 'REJECT' })">驳回</button>
      <button class="approve flex-1" :disabled="acting" @click="$emit('review', { kind, item, action: 'APPROVE' })">{{ kind === 'makeup' ? '通过并补写打卡' : '通过并写请假留痕' }}</button>
    </view>
  </view>
</template>

<script>
export default {
  props: {
    item: { type: Object, required: true },
    kind: { type: String, required: true },
    acting: { type: Boolean, default: false }
  },
  emits: ['review']
}
</script>

<style scoped>
.item-card{display:flex;flex-direction:column;gap:14rpx}.title{font-size:30rpx;font-weight:600}.sub{display:block;margin-top:4rpx;color:var(--text-tertiary);font-size:24rpx}.detail{display:flex;gap:20rpx;font-size:26rpx}.key{width:130rpx;color:var(--text-tertiary);flex-shrink:0}.actions{display:flex;gap:16rpx;margin-top:4rpx}.reject,.approve{min-height:88rpx;border-radius:16rpx;font-size:28rpx}.reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.approve{border:0;background:var(--teacher-600);color:#fff}.reject::after,.approve::after{border:0}.reject[disabled],.approve[disabled]{opacity:.55}
</style>
