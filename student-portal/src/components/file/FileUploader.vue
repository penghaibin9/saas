<script setup>
import { ref } from 'vue'
import { fileSdk } from '../../services/fileSdk'

const props = defineProps({
  bizType: { type: String, default: 'ATTACHMENT' },
  bizId: { type: [String, Number], default: '' },
  accept: { type: String, default: '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.gif,.zip,.txt,.csv' },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['uploaded', 'error'])
const inputRef = ref(null)
const uploading = ref(false)

async function handleChange(event) {
  const file = event.target?.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    emit('uploaded', await fileSdk.upload(file, { bizType: props.bizType, bizId: props.bizId }))
  } catch (error) {
    emit('error', error)
  } finally {
    uploading.value = false
    if (inputRef.value) inputRef.value.value = ''
  }
}
</script>

<template>
  <label class="student-file-uploader" :class="{ 'is-disabled': disabled || uploading }">
    <input ref="inputRef" type="file" :accept="accept" :disabled="disabled || uploading" @change="handleChange" />
    <span>{{ uploading ? '正在上传…' : '选择并上传文件' }}</span>
  </label>
</template>

<style scoped>
.student-file-uploader { display: inline-flex; align-items: center; justify-content: center; min-height: 40px; padding: 0 18px; border-radius: 9px; background: #1769e0; color: #fff; cursor: pointer; }
.student-file-uploader input { display: none; }
.student-file-uploader.is-disabled { cursor: not-allowed; opacity: .55; }
</style>
