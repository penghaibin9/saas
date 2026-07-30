<script setup>
import { ref } from 'vue'
import { fileSdk } from '../../services/fileSdk'

const props = defineProps({ file: { type: Object, default: null } })
const emit = defineEmits(['error'])
const busy = ref(false)

async function openFile() {
  if (!props.file?.fileId || busy.value) return
  busy.value = true
  try {
    await fileSdk.preview(props.file.fileId, props.file.fileName)
  } catch (error) {
    emit('error', error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="file" class="student-file-previewer">
    <div><strong>{{ file.fileName || '未命名文件' }}</strong><small>{{ file.statusText || '状态未知' }}</small></div>
    <button v-if="file.canPreview || file.canDownload" type="button" :disabled="busy" @click="openFile">
      {{ busy ? '正在打开…' : '打开文件' }}
    </button>
    <span v-else>文件尚未安全可用</span>
  </div>
</template>

<style scoped>
.student-file-previewer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; border-radius: 10px; background: #f7faff; }
.student-file-previewer > div { min-width: 0; display: grid; gap: 4px; }
.student-file-previewer strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.student-file-previewer small, .student-file-previewer span { color: #79869a; }
.student-file-previewer button { min-height: 34px; padding: 0 14px; border: 1px solid #cbd8ea; border-radius: 8px; background: #fff; color: #1769e0; cursor: pointer; }
</style>
