<script setup>
import { ref } from 'vue'
import { fileSdk } from '@/services/fileSdk'

const props = defineProps({ file: { type: Object, default: null } })
const emit = defineEmits(['error'])
const busy = ref(false)

async function openFile() {
  if (!props.file?.fileId || busy.value) return
  busy.value = true
  try {
    await fileSdk.open(props.file.fileId)
  } catch (error) {
    emit('error', error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <view v-if="file" class="mini-file-previewer">
    <view class="mini-file-previewer__meta">
      <text class="mini-file-previewer__name">{{ file.fileName || '未命名文件' }}</text>
      <text class="mini-file-previewer__status">{{ file.statusText || '状态未知' }}</text>
    </view>
    <button v-if="file.canPreview || file.canDownload" class="mini-file-previewer__button" size="mini" :disabled="busy" @click="openFile">
      {{ busy ? '打开中…' : '打开' }}
    </button>
    <text v-else class="mini-file-previewer__locked">文件尚未安全可用</text>
  </view>
</template>

<style scoped>
.mini-file-previewer { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; padding: 24rpx 26rpx; border-radius: 18rpx; background: #f7faff; }
.mini-file-previewer__meta { min-width: 0; display: flex; flex: 1; flex-direction: column; gap: 8rpx; }
.mini-file-previewer__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #24324a; font-weight: 600; }
.mini-file-previewer__status, .mini-file-previewer__locked { color: #7b8798; font-size: 24rpx; }
.mini-file-previewer__button { flex: none; margin: 0; border: 1rpx solid #cbd8ea; background: #fff; color: #1769e0; }
</style>
