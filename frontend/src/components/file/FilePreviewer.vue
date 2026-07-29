<script setup>
import { ref } from 'vue'
import { fileSdk } from '@/services/file/fileSdk'

const props = defineProps({
  file: { type: Object, default: null }
})
const emit = defineEmits(['error'])
const busy = ref(false)

async function run(action) {
  if (!props.file?.fileId || busy.value) return
  busy.value = true
  try {
    await fileSdk[action](props.file.fileId, props.file.fileName)
  } catch (error) {
    emit('error', error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="file" class="file-previewer">
    <div class="file-previewer__meta">
      <strong>{{ file.fileName || '未命名文件' }}</strong>
      <span>{{ file.statusText || '状态未知' }}</span>
    </div>
    <div class="file-previewer__actions">
      <button v-if="file.canPreview" type="button" :disabled="busy" @click="run('preview')">预览</button>
      <button v-if="file.canDownload" type="button" :disabled="busy" @click="run('download')">下载</button>
      <span v-if="!file.canPreview && !file.canDownload">文件尚未安全可用</span>
    </div>
  </div>
</template>

<style scoped>
.file-previewer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid #dfe7f2; border-radius: 10px; background: #f8fbff; }
.file-previewer__meta { min-width: 0; display: grid; gap: 4px; }
.file-previewer__meta strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #23314a; }
.file-previewer__meta span, .file-previewer__actions span { color: #778499; font-size: 13px; }
.file-previewer__actions { display: flex; align-items: center; gap: 8px; flex: none; }
.file-previewer__actions button { min-height: 32px; padding: 0 12px; border: 1px solid #cbd8ea; border-radius: 7px; background: #fff; color: #1769e0; cursor: pointer; }
.file-previewer__actions button:disabled { opacity: .55; cursor: wait; }
</style>
