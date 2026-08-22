<script setup>
import { ref } from 'vue'
import { fileSdk } from '../../services/fileSdk'
import StudentDocumentViewer from './viewer/StudentDocumentViewer.vue'

const props = defineProps({ file: { type: Object, default: null } })
const emit = defineEmits(['error'])
const busy = ref(false)
const readerOpen = ref(false)

function openFile() {
  if (!props.file?.fileId || busy.value || props.file?.canPreview !== true) return
  readerOpen.value = true
}

async function loadPreview(file, options) {
  if (!file?.fileId || file?.canPreview !== true) throw new Error('当前文件未授予站内预览权限')
  return fileSdk.fetchPreviewBlob(file.fileId, options)
}

async function downloadFile(file = props.file) {
  if (!file?.fileId || busy.value || file?.canDownload !== true) return
  busy.value = true
  try { await fileSdk.download(file.fileId, file.fileName) } catch (error) { emit('error', error) } finally { busy.value = false }
}
</script>

<template>
  <div v-if="file" class="student-file-previewer">
    <div><strong>{{ file.fileName || '未命名文件' }}</strong><small>{{ file.statusText || '状态未知' }}</small></div>
    <nav>
      <button v-if="file.canPreview" type="button" :disabled="busy" @click="openFile">站内查看</button>
      <button v-if="file.canDownload" type="button" :disabled="busy" @click="downloadFile(file)">下载</button>
      <span v-if="!file.canPreview && !file.canDownload">文件尚未安全可用</span>
    </nav>
  </div>
  <StudentDocumentViewer v-if="readerOpen && file" :file="file" :load-preview="loadPreview" @download="downloadFile" @close="readerOpen = false" />
</template>

<style scoped>
.student-file-previewer{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-radius:10px;background:#f7faff}.student-file-previewer>div{min-width:0;display:grid;gap:4px}.student-file-previewer strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.student-file-previewer small,.student-file-previewer span{color:#79869a}.student-file-previewer nav{display:flex;align-items:center;gap:8px;flex:none}.student-file-previewer button{min-height:34px;padding:0 14px;border:1px solid #cbd8ea;border-radius:8px;background:#fff;color:#1769e0;cursor:pointer}.student-file-previewer button:disabled{opacity:.55;cursor:not-allowed}
</style>
