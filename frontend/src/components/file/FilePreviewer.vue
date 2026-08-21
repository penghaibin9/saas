<script setup>
import { computed, ref } from 'vue'
import { fileSdk } from '@/services/file/fileSdk'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'

const props = defineProps({
  file: { type: Object, default: null },
  inline: { type: Boolean, default: false },
  provider: { type: Object, default: null },
  allowDownload: { type: Boolean, default: true },
  downloadHandler: { type: Function, default: null }
})
const emit = defineEmits(['error', 'download'])
const busy = ref(false)
const expanded = ref(false)

const descriptor = computed(() => props.file ? buildPreviewDescriptorFromFile(props.file) : null)
const canInlinePreview = computed(() => Boolean(props.inline && props.provider && descriptor.value?.canPreview))

async function run(action) {
  if (!props.file?.fileId || busy.value) return
  if (action === 'preview' && canInlinePreview.value) {
    expanded.value = !expanded.value
    return
  }
  busy.value = true
  try {
    if (action === 'download' && props.downloadHandler) await props.downloadHandler(props.file)
    else await fileSdk[action](props.file.fileId, props.file.fileName)
    if (action === 'download') emit('download', props.file)
  } catch (error) {
    emit('error', error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="file" class="file-previewer" :class="{ 'is-expanded': expanded }">
    <div class="file-previewer__bar">
      <div class="file-previewer__meta">
        <strong>{{ file.fileName || '未命名文件' }}</strong>
        <span>{{ file.statusText || '状态未知' }}</span>
      </div>
      <div class="file-previewer__actions">
        <button v-if="file.canPreview" type="button" :disabled="busy" @click="run('preview')">
          {{ canInlinePreview && expanded ? '收起预览' : '预览' }}
        </button>
        <button v-if="file.canDownload && allowDownload" type="button" :disabled="busy" @click="run('download')">下载</button>
        <span v-if="!file.canPreview && !file.canDownload">文件尚未安全可用</span>
      </div>
    </div>

    <AppDocumentViewer
      v-if="canInlinePreview && expanded"
      class="file-previewer__viewer"
      :descriptor="descriptor"
      :provider="provider"
      :versions="[file]"
      :files="[file]"
      :active-file-key="file.fileId"
      :active-version-id="file.fileVersionId ?? file.versionId ?? null"
      :canonical-version-id="file.fileVersionId ?? file.versionId ?? null"
      :allow-download="Boolean(allowDownload && file.canDownload)"
      :show-version-bar="false"
      :show-file-switcher="false"
      @download="run('download')"
    />
  </div>
</template>

<style scoped>
.file-previewer { display: grid; gap: 10px; padding: 14px 16px; border: 1px solid #dfe7f2; border-radius: 10px; background: #f8fbff; }
.file-previewer__bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.file-previewer__meta { min-width: 0; display: grid; gap: 4px; }
.file-previewer__meta strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #23314a; }
.file-previewer__meta span, .file-previewer__actions span { color: #778499; font-size: 13px; }
.file-previewer__actions { display: flex; align-items: center; gap: 8px; flex: none; }
.file-previewer__actions button { min-height: 32px; padding: 0 12px; border: 1px solid #cbd8ea; border-radius: 7px; background: #fff; color: #1769e0; cursor: pointer; }
.file-previewer__actions button:disabled { opacity: .55; cursor: wait; }
.file-previewer__viewer { min-height: 560px; background: #fff; }
@media (max-width: 900px) { .file-previewer__bar { align-items: flex-start; flex-direction: column; } .file-previewer__actions { width: 100%; } }
</style>
