<template>
  <div class="docx-viewer-adapter">
    <div v-if="rendering" class="docx-viewer-adapter__loading">正在安全解析并排版 DOCX…</div>
    <div ref="host" class="docx-viewer-adapter__host" :style="{ '--docx-zoom': zoom }"></div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { buildDocxPreview } from './docx-preview-renderer'

const props = defineProps({
  source: { type: [Blob, ArrayBuffer, Uint8Array], required: true },
  generation: { type: Number, default: 0 },
  zoom: { type: Number, default: 1 }
})
const emit = defineEmits(['ready', 'error'])
const host = ref(null)
const rendering = ref(false)
let activeRender = 0
let disposePreview = null

function dispose() {
  activeRender += 1
  try { disposePreview?.() } catch { /* object URL cleanup must not block teardown */ }
  disposePreview = null
  host.value?.replaceChildren()
}

async function render() {
  const renderId = activeRender + 1
  activeRender = renderId
  rendering.value = true
  try { disposePreview?.() } catch { /* cleanup only */ }
  disposePreview = null
  host.value?.replaceChildren()
  await nextTick()
  try {
    const result = await buildDocxPreview(props.source)
    if (renderId !== activeRender || !host.value) {
      result.dispose()
      return
    }
    host.value.replaceChildren(result.element)
    disposePreview = result.dispose
    rendering.value = false
    emit('ready', { pageCount: 0 })
  } catch (error) {
    if (renderId !== activeRender) return
    rendering.value = false
    emit('error', error)
  }
}

watch(() => [props.source, props.generation], render, { immediate: true })
onBeforeUnmount(dispose)
</script>

<style scoped>
.docx-viewer-adapter{height:100%;overflow:auto;background:#e9eef5;position:relative;padding:18px}.docx-viewer-adapter__loading{position:sticky;top:8px;z-index:2;width:max-content;margin:0 auto 10px;padding:7px 12px;border-radius:999px;background:rgba(15,23,42,.86);color:#fff;font-size:12px}.docx-viewer-adapter__host{min-height:100%;display:grid;justify-items:center}.docx-viewer-adapter__host :deep(.docx-local-preview){width:min(900px,100%);zoom:var(--docx-zoom);font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",Arial,sans-serif;color:#1f2937}.docx-viewer-adapter__host :deep(.docx-local-preview__page){min-height:1120px;padding:76px 82px;margin:0 auto;background:#fff;box-shadow:0 8px 28px rgba(15,23,42,.12);line-height:1.75;box-sizing:border-box}.docx-viewer-adapter__host :deep(.docx-local-preview__paragraph){margin:0 0 10px;white-space:pre-wrap;overflow-wrap:anywhere}.docx-viewer-adapter__host :deep(.docx-local-preview__heading){margin:18px 0 10px;line-height:1.45}.docx-viewer-adapter__host :deep(.docx-local-preview__image){display:block;max-width:100%;height:auto;margin:10px auto}.docx-viewer-adapter__host :deep(.docx-local-preview__table){width:100%;border-collapse:collapse;margin:12px 0}.docx-viewer-adapter__host :deep(.docx-local-preview__table td){border:1px solid #cbd5e1;padding:7px;vertical-align:top}.docx-viewer-adapter__host :deep(.docx-local-preview__table p){margin:0 0 5px}.docx-viewer-adapter__host :deep(.docx-local-preview__hyperlink-text){color:#2563eb;text-decoration:underline}.docx-viewer-adapter__host :deep(.docx-local-preview__list-marker){color:#475569}@media(max-width:760px){.docx-viewer-adapter{padding:8px}.docx-viewer-adapter__host :deep(.docx-local-preview__page){min-height:0;padding:28px 22px}}
</style>
