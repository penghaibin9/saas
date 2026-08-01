<script setup>
defineProps({ items: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])
</script>

<template>
  <view class="mini-file-timeline">
    <view v-if="!items.length" class="mini-file-timeline__empty">暂无历史版本</view>
    <view v-for="item in items" v-else :key="item.bindingId || `${item.file?.fileId}-${item.versionNo}`" class="mini-file-timeline__item" @click="emit('select', item)">
      <view class="mini-file-timeline__head">
        <text>版本 {{ item.versionNo }}</text>
        <text v-if="item.isCurrent" class="mini-file-timeline__current">当前</text>
      </view>
      <text class="mini-file-timeline__name">{{ item.file?.fileName || '未命名文件' }}</text>
      <text class="mini-file-timeline__meta">{{ item.file?.statusText || '状态未知' }} · {{ item.boundAt || '-' }}</text>
    </view>
  </view>
</template>

<style scoped>
.mini-file-timeline { display: flex; flex-direction: column; gap: 16rpx; }
.mini-file-timeline__item { display: flex; flex-direction: column; gap: 8rpx; padding: 22rpx 24rpx; border: 1rpx solid #e1e8f2; border-radius: 18rpx; background: #fff; }
.mini-file-timeline__head { display: flex; align-items: center; gap: 12rpx; color: #1769e0; font-size: 26rpx; }
.mini-file-timeline__current { padding: 2rpx 12rpx; border-radius: 999rpx; background: #e8f2ff; font-size: 22rpx; }
.mini-file-timeline__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #24324a; font-weight: 600; }
.mini-file-timeline__meta, .mini-file-timeline__empty { color: #7b8798; font-size: 24rpx; }
.mini-file-timeline__empty { padding: 36rpx; text-align: center; }
</style>
