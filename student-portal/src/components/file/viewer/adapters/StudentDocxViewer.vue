<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { buildDocxPreview } from './docx-preview-renderer'

const props = defineProps({ source: { type: Blob, default: null } })
const host = ref(null)
const loading = ref(false)
const error = ref('')
let generation = 0
let disposePreview = null

async function render() {
  generation += 1
  const current = generation
  try { disposePreview?.() } catch { /* cleanup only */ }
  disposePreview = null
  host.value?.replaceChildren()
  error.value = ''
  if (!props.source) return
  loading.value = true
  await nextTick()
  try {
    const result = await buildDocxPreview(props.source)
    if (current !== generation || !host.value) { result.dispose(); return }
    host.value.replaceChildren(result.element)
    disposePreview = result.dispose
  } catch (e) {
    if (current === generation) error.value = e?.message || 'DOCX 站内预览失败'
  } finally {
    if (current === generation) loading.value = false
  }
}

watch(() => props.source, render, { immediate: true })
onBeforeUnmount(() => {
  generation += 1
  try { disposePreview?.() } catch { /* cleanup only */ }
  host.value?.replaceChildren()
})
</script>

<template>
  <div class="student-docx-viewer">
    <div v-if="loading" class="student-docx-viewer__state">正在安全解析 DOCX…</div>
    <div v-else-if="error" class="student-docx-viewer__state is-error">{{ error }}</div>
    <div ref="host" class="student-docx-viewer__host"></div>
  </div>
</template>

<style scoped>
.student-docx-viewer{height:100%;overflow:auto;padding:16px;background:#e9eef5}.student-docx-viewer__state{position:sticky;top:8px;z-index:2;width:max-content;max-width:calc(100% - 24px);margin:0 auto 10px;padding:7px 12px;border-radius:999px;background:rgba(15,23,42,.86);color:#fff;font-size:12px}.student-docx-viewer__state.is-error{background:#991b1b}.student-docx-viewer__host{display:grid;justify-items:center}.student-docx-viewer__host :deep(.docx-local-preview){width:min(900px,100%);font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;color:#1f2937}.student-docx-viewer__host :deep(.docx-local-preview__page){min-height:1060px;padding:68px 76px;background:#fff;box-shadow:0 8px 28px rgba(15,23,42,.12);line-height:1.75;box-sizing:border-box}.student-docx-viewer__host :deep(.docx-local-preview__paragraph){margin:0 0 10px;white-space:pre-wrap;overflow-wrap:anywhere}.student-docx-viewer__host :deep(.docx-local-preview__heading){margin:18px 0 10px}.student-docx-viewer__host :deep(.docx-local-preview__image){display:block;max-width:100%;height:auto;margin:10px auto}.student-docx-viewer__host :deep(.docx-local-preview__table){width:100%;border-collapse:collapse;margin:12px 0}.student-docx-viewer__host :deep(.docx-local-preview__table td){border:1px solid #cbd5e1;padding:7px;vertical-align:top}.student-docx-viewer__host :deep(.docx-local-preview__hyperlink-text){color:#2563eb;text-decoration:underline}@media(max-width:720px){.student-docx-viewer{padding:7px}.student-docx-viewer__host :deep(.docx-local-preview__page){min-height:0;padding:26px 20px}}
</style>
