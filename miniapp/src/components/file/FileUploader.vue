<script setup>
import { ref } from 'vue'
import { fileSdk } from '@/services/fileSdk'

const props = defineProps({
  bizType: { type: String, default: 'ATTACHMENT' },
  bizId: { type: [String, Number], default: '' },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['uploaded', 'error'])
const uploading = ref(false)

async function chooseAndUpload() {
  if (props.disabled || uploading.value) return
  uploading.value = true
  try {
    const file = await fileSdk.choose()
    if (!file) return
    emit('uploaded', await fileSdk.upload(file, { bizType: props.bizType, bizId: props.bizId }))
  } catch (error) {
    emit('error', error)
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <button class="mini-file-uploader" :disabled="disabled || uploading" @click="chooseAndUpload">
    {{ uploading ? '正在上传…' : '选择并上传文件' }}
  </button>
</template>

<style scoped>
.mini-file-uploader { display: flex; align-items: center; justify-content: center; min-height: 76rpx; padding: 0 28rpx; border: 0; border-radius: 16rpx; background: #1769e0; color: #fff; font-size: 28rpx; }
.mini-file-uploader[disabled] { opacity: .55; }
</style>
