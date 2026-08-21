<script setup>
import { computed, shallowRef, watch } from 'vue'
import StudentDocumentState from './StudentDocumentState.vue'
import StudentDocumentToolbar from './StudentDocumentToolbar.vue'
import StudentDocumentVersionBar from './StudentDocumentVersionBar.vue'
import StudentDocxViewer from './adapters/StudentDocxViewer.vue'
import StudentImageViewer from './adapters/StudentImageViewer.vue'
import StudentPdfViewer from './adapters/StudentPdfViewer.vue'
import StudentUnsupportedViewer from './adapters/StudentUnsupportedViewer.vue'
import { useStudentPreviewSession } from './useStudentPreviewSession'

const props = defineProps({
  file: { type: Object, required: true },
  versions: { type: Array, default: () => [] },
  loadPreview: { type: Function, required: true },
  readOnly: { type: Boolean, default: false }
})
const emit = defineEmits(['close', 'download', 'select-version'])
const selectedFile = shallowRef(props.file)
const session = useStudentPreviewSession((file, options) => props.loadPreview(file, options))

function versionFile(item = {}) {
  const nested = item.file || {}
  return {
    ...nested,
    ...item,
    fileId: item.fileId || nested.fileId,
    fileName: item.fileName || nested.fileName,
    mimeType: item.mimeType || nested.mimeType,
    canDownload: item.canDownload ?? nested.canDownload,
    canPreview: item.canPreview ?? nested.canPreview
  }
}

const normalizedVersions = computed(() => props.versions.map(versionFile).filter((item) => item.fileId))
const isReadOnly = computed(() => props.readOnly || selectedFile.value?.isCurrent === false)
const canDownload = computed(() => selectedFile.value?.canDownload !== false)
const extension = computed(() => String(selectedFile.value?.fileName || '').toLowerCase().split('.').pop() || '')
const effectiveMime = computed(() => String(session.mimeType.value || selectedFile.value?.mimeType || '').toLowerCase())
const kind = computed(() => {
  if (effectiveMime.value.includes('pdf') || extension.value === 'pdf') return 'pdf'
  if (effectiveMime.value.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(extension.value)) return 'image'
  if (effectiveMime.value === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' || extension.value === 'docx') return 'docx'
  return 'unsupported'
})

watch(() => props.file, (file) => { selectedFile.value = file; session.open(file) }, { immediate: true })

function selectVersion(item) {
  const next = versionFile(item)
  selectedFile.value = next
  emit('select-version', next)
  session.open(next)
}
</script>

<template>
  <div class="student-document-reader" role="dialog" aria-modal="true" aria-label="站内文件阅读器">
    <div class="student-document-reader__shell">
      <StudentDocumentToolbar :file="selectedFile" :read-only="isReadOnly" :can-download="canDownload" @download="emit('download', selectedFile)" @close="emit('close')" />
      <StudentDocumentVersionBar :items="normalizedVersions" :active-file="selectedFile" @select="selectVersion" />
      <main class="student-document-reader__body">
        <StudentDocumentState v-if="session.status.value !== 'ready'" :status="session.status.value" :error="session.error.value" @retry="session.retry(selectedFile)" />
        <StudentPdfViewer v-else-if="kind === 'pdf'" :url="session.objectUrl.value" :title="selectedFile.fileName" />
        <StudentImageViewer v-else-if="kind === 'image'" :url="session.objectUrl.value" :alt="selectedFile.fileName" />
        <StudentDocxViewer v-else-if="kind === 'docx'" :source="session.blob.value" />
        <StudentUnsupportedViewer v-else :file-name="selectedFile.fileName" :can-download="canDownload" @download="emit('download', selectedFile)" />
      </main>
      <footer v-if="isReadOnly" class="student-document-reader__readonly">你正在查看只读冻结版本；阅读器不会修改、替换或推进该业务文件。</footer>
    </div>
  </div>
</template>

<style scoped>
.student-document-reader{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;padding:22px;background:rgba(12,24,42,.58)}.student-document-reader__shell{width:min(1180px,100%);height:min(88vh,920px);display:flex;flex-direction:column;overflow:hidden;border-radius:14px;background:#fff;box-shadow:0 24px 80px rgba(11,27,52,.3)}.student-document-reader__body{min-height:0;flex:1;overflow:auto;background:#eef2f7}.student-document-reader__readonly{padding:8px 14px;border-top:1px solid #ead9b7;background:#fff9ec;color:#7a5200;font-size:12px}@media(max-width:720px){.student-document-reader{padding:0}.student-document-reader__shell{width:100%;height:100%;max-height:none;border-radius:0}}
</style>
