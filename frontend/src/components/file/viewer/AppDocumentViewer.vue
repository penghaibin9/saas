<template>
  <AppDocumentFullscreen v-model:active="fullscreen">
    <div class="document-viewer" :data-preview-identity="identity">
      <AppDocumentVersionBar v-if="showVersionBar" :versions="versions" :active-version-id="activeVersionId" :canonical-version-id="canonicalVersionId" @select="$emit('select-version', $event)" />
      <AppDocumentFileSwitcher v-if="showFileSwitcher" :files="files" :active-file-key="activeFileKey" @select="$emit('select-file', $event)" />
      <AppDocumentToolbar
        :page="page" :page-count="pageCount" :zoom="zoom" :fullscreen="fullscreen"
        :allow-download="downloadAllowed"
        @page="setPage" @zoom="zoom = $event" @fullscreen="fullscreen = !fullscreen" @download="$emit('download', normalizedDescriptor)"
      />
      <div class="document-viewer__body">
        <AppDocumentState v-if="state.status !== 'READY' && state.status !== 'UNSUPPORTED'" :state="state.status" :error="state.error" @retry="retry" />
        <UnsupportedViewerAdapter v-else-if="state.status === 'UNSUPPORTED'" :allow-download="downloadAllowed" @download="$emit('download', normalizedDescriptor)" />
        <PdfViewerAdapter
          v-else-if="normalizedDescriptor?.previewKind === 'PDF' && source"
          ref="pdfViewer" :source="source" :generation="state.generation" :page="page" :zoom="zoom"
          @ready="onPdfReady" @page-change="page = $event" @error="onRenderError"
        />
        <ImageViewerAdapter
          v-else-if="normalizedDescriptor?.previewKind === 'IMAGE' && source"
          :source="source" :file-name="normalizedDescriptor?.fileName" @error="onRenderError"
        />
      </div>
    </div>
  </AppDocumentFullscreen>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppDocumentFullscreen from './AppDocumentFullscreen.vue'
import AppDocumentToolbar from './AppDocumentToolbar.vue'
import AppDocumentVersionBar from './AppDocumentVersionBar.vue'
import AppDocumentFileSwitcher from './AppDocumentFileSwitcher.vue'
import AppDocumentState from './AppDocumentState.vue'
import PdfViewerAdapter from './adapters/PdfViewerAdapter.vue'
import ImageViewerAdapter from './adapters/ImageViewerAdapter.vue'
import UnsupportedViewerAdapter from './adapters/UnsupportedViewerAdapter.vue'
import { normalizePreviewDescriptor, previewIdentity } from './viewer-contract'
import { usePreviewSession } from './usePreviewSession'

const props = defineProps({
  descriptor: { type: Object, default: null }, provider: { type: Object, required: true },
  versions: { type: Array, default: () => [] }, files: { type: Array, default: () => [] },
  activeFileKey: { type: [String, Number], default: null }, activeVersionId: { type: [String, Number], default: null },
  canonicalVersionId: { type: [String, Number], default: null }, mode: { type: String, default: 'embedded' },
  readonly: { type: Boolean, default: true }, allowDownload: { type: Boolean, default: false },
  showVersionBar: { type: Boolean, default: true }, showFileSwitcher: { type: Boolean, default: true },
  restoreKey: { type: String, default: '' }, watermarkPolicy: { type: Object, default: null }
})
defineEmits(['select-version', 'select-file', 'download', 'preview-error'])
const normalizedDescriptor = computed(() => props.descriptor ? normalizePreviewDescriptor(props.descriptor) : null)
const identity = computed(() => normalizedDescriptor.value ? previewIdentity(normalizedDescriptor.value) : '')
const { state, source, load, retry } = usePreviewSession(props.provider)
const page = ref(1); const pageCount = ref(0); const zoom = ref(1); const fullscreen = ref(props.mode === 'fullscreen')
const pdfViewer = ref(null)
const downloadAllowed = computed(() => Boolean(props.allowDownload && normalizedDescriptor.value?.canDownload))

function setPage(value) { page.value = Math.min(Math.max(Number(value) || 1, 1), pageCount.value || 1); pdfViewer.value?.goToPage?.(page.value) }
function onPdfReady({ pageCount: count }) { pageCount.value = Number(count || 0); setPage(Math.min(page.value, pageCount.value || 1)) }
function onRenderError(error) { state.status = 'ERROR'; state.error = { code: error?.code || 'PREVIEW_RENDER_FAILED', message: error?.message || '文档渲染失败，请重试', retryable: true } }
watch(identity, () => { page.value = 1; pageCount.value = 0; zoom.value = 1; load(normalizedDescriptor.value) }, { immediate: true })
</script>

<style scoped>
.document-viewer{min-width:0;border:1px solid var(--border-light,#e2e8f0);border-radius:10px;overflow:hidden;background:var(--card,#fff);height:100%;display:flex;flex-direction:column}.document-viewer__body{flex:1;min-height:520px;min-width:0;overflow:hidden}.is-fullscreen .document-viewer{height:100vh;border:0;border-radius:0}
</style>
