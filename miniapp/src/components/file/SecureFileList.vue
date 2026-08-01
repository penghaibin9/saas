<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['open', 'refresh'])
</script>

<template>
  <view class="mini-file-list">
    <view class="mini-file-list__header">
      <text class="mini-file-list__title">安全文件</text>
      <text class="mini-file-list__refresh" @click="emit('refresh')">刷新</text>
    </view>
    <view v-if="loading" class="mini-file-list__empty">正在加载…</view>
    <view v-else-if="!items.length" class="mini-file-list__empty">暂无文件</view>
    <view v-for="item in items" v-else :key="item.fileId" class="mini-file-list__item">
      <view class="mini-file-list__main">
        <text class="mini-file-list__name">{{ item.fileName || '未命名文件' }}</text>
        <text class="mini-file-list__status">{{ item.statusText || '状态未知' }}</text>
      </view>
      <button v-if="item.canPreview || item.canDownload" class="mini-file-list__action" size="mini" @click="emit('open', item)">打开</button>
      <text v-else class="mini-file-list__locked">暂不可使用</text>
    </view>
  </view>
</template>

<style scoped>
.mini-file-list { overflow: hidden; border: 1rpx solid #e1e8f2; border-radius: 20rpx; background: #fff; }
.mini-file-list__header, .mini-file-list__item { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; padding: 24rpx 26rpx; border-bottom: 1rpx solid #edf1f6; }
.mini-file-list__item:last-child { border-bottom: 0; }
.mini-file-list__title, .mini-file-list__name { color: #24324a; font-weight: 600; }
.mini-file-list__refresh, .mini-file-list__action { color: #1769e0; }
.mini-file-list__main { min-width: 0; display: flex; flex: 1; flex-direction: column; gap: 8rpx; }
.mini-file-list__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 28rpx; }
.mini-file-list__status, .mini-file-list__locked { color: #7b8798; font-size: 24rpx; }
.mini-file-list__action { flex: none; margin: 0; border: 1rpx solid #cbd8ea; background: #fff; }
.mini-file-list__empty { padding: 44rpx 24rpx; text-align: center; color: #7b8798; }
</style>
