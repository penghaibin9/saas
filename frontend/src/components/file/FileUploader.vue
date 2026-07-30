<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { fileSdk } from '@/services/file/fileSdk'

const props = defineProps({
  bizType: { type: String, default: 'ATTACHMENT' },
  bizId: { type: [String, Number], default: '' },
  accept: { type: String, default: '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.gif,.zip,.txt,.csv' },
  disabled: { type: Boolean, default: false },
  buttonText: { type: String, default: '上传文件' }
})
const emit = defineEmits(['uploaded', 'progress', 'error', 'cancelled'])

const inputRef = ref(null)
const uploading = ref(false)
const progress = ref(0)
const fileName = ref('')
let activeTask = null

function chooseFile() {
  if (!props.disabled && !uploading.value) inputRef.value?.click()
}

async function handleChange(event) {
  const file = event.target?.files?.[0]
  if (!file) return
  fileName.value = file.name || ''
  progress.value = 0
  uploading.value = true
  activeTask = fileSdk.upload(file, {
    bizType: props.bizType,
    bizId: props.bizId,
    onProgress(value) {
      progress.value = value
      emit('progress', value)
    }
  })
  try {
    const result = await activeTask.promise
    emit('uploaded', result)
  } catch (error) {
    if (error?.cancelled) emit('cancelled')
    else emit('error', error)
  } finally {
    uploading.value = false
    activeTask = null
    if (inputRef.value) inputRef.value.value = ''
  }
}

function cancelUpload() {
  activeTask?.cancel()
}

onBeforeUnmount(() => activeTask?.cancel())
</script>

<template>
  <div class="file-uploader">
    <input ref="inputRef" class="file-uploader__input" type="file" :accept="accept" @change="handleChange" />
    <button class="file-uploader__button" type="button" :disabled="disabled || uploading" @click="chooseFile">
      {{ uploading ? `上传中 ${progress}%` : buttonText }}
    </button>
    <button v-if="uploading" class="file-uploader__cancel" type="button" @click="cancelUpload">取消</button>
    <div v-if="uploading" class="file-uploader__progress" aria-live="polite">
      <div class="file-uploader__bar" :style="{ width: `${progress}%` }" />
    </div>
    <span v-if="fileName" class="file-uploader__name">{{ fileName }}</span>
  </div>
</template>

<style scoped>
.file-uploader { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.file-uploader__input { display: none; }
.file-uploader__button, .file-uploader__cancel { min-height: 36px; padding: 0 16px; border-radius: 8px; border: 1px solid #d7e3f4; background: #fff; cursor: pointer; }
.file-uploader__button { background: #1769e0; border-color: #1769e0; color: #fff; }
.file-uploader__button:disabled { cursor: not-allowed; opacity: .55; }
.file-uploader__progress { width: 180px; height: 7px; overflow: hidden; border-radius: 999px; background: #e8eef8; }
.file-uploader__bar { height: 100%; border-radius: inherit; background: currentColor; transition: width .2s ease; }
.file-uploader__name { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #52627a; font-size: 13px; }
</style>
