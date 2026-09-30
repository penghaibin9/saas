<template>
  <div class="gd-upload-status" :data-upload-state="status.phase" :data-file-id="file.fileId">
    <div class="gd-upload-status__message" role="status" aria-live="polite" aria-atomic="true">
      <strong>{{ file.fileName || '已上传文件' }}</strong>
      <span>{{ status.message }}</span>
    </div>
    <div class="gd-upload-status__actions">
      <button
        v-if="status.phase !== 'ready'"
        type="button"
        class="sp-btn sp-btn--ghost"
        :disabled="locked || status.phase === 'checking'"
        @click="recheck"
      >{{ status.phase === 'checking' ? '正在检查…' : '重新检查文件状态' }}</button>
      <button
        v-if="status.phase === 'ready' && file.canPreview"
        type="button"
        class="sp-btn sp-btn--ghost"
        :disabled="locked"
        @click="$emit('preview')"
      >{{ previewLabel }}</button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { fileSdk } from '../../services/fileSdk'
import { createGraduationUploadMonitor } from '../../services/graduationUploadReadiness'

const props = defineProps({
  file: { type: Object, required: true },
  locked: { type: Boolean, default: false },
  previewLabel: { type: String, default: '预览我将提交的文件' }
})
const emit = defineEmits(['update:file', 'preview'])
const status = ref({ phase: 'idle', message: '' })
const monitor = createGraduationUploadMonitor({
  readMetadata: (fileId) => fileSdk.metadata(fileId),
  onFile: (fresh) => {
    if (String(props.file?.fileId || '') === String(fresh.fileId || '')) {
      emit('update:file', fresh)
    }
  },
  onState: (value) => { status.value = value }
})

// Pause background reads for a submission. Its explicit final check owns the
// file until the command ends; resume from that check's latest server state.
watch(() => [String(props.file?.fileId || ''), props.locked], () => {
  monitor.stop()
  if (!props.locked) void monitor.start(props.file)
}, { immediate: true, flush: 'sync' })

function recheck() {
  if (props.locked) return
  void monitor.recheck()
}
onBeforeUnmount(() => monitor.stop())
</script>

<style scoped>
.gd-upload-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #dce7f5;
  border-radius: 10px;
  background: #f4f8ff;
}
.gd-upload-status__message { display: grid; min-width: 0; flex: 1 1 220px; gap: 3px; }
.gd-upload-status__message strong { overflow-wrap: anywhere; color: #263b55; font-size: 13px; }
.gd-upload-status__message span { color: #53657b; font-size: 13px; line-height: 1.5; }
.gd-upload-status__actions { display: flex; flex-wrap: wrap; gap: 8px; }
.gd-upload-status[data-upload-state='blocked'],
.gd-upload-status[data-upload-state='error'] { border-color: #f4c6c3; background: #fff7f6; }
.gd-upload-status[data-upload-state='ready'] { border-color: #b9e0cf; background: #f3fbf7; }
</style>
