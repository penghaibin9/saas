<template><div class="image-viewer" data-preview-adapter="image"><img v-if="url" :src="url" :alt="fileName || '文件图片预览'" /></div></template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ source: { type: [Blob, ArrayBuffer, Uint8Array], required: true }, fileName: { type: String, default: '' } })
const emit = defineEmits(['ready', 'error'])
const url = ref('')
function revoke() { if (url.value) URL.revokeObjectURL(url.value); url.value = '' }
function makeBlob(source) {
  if (source instanceof Blob) return source
  if (source instanceof ArrayBuffer || source instanceof Uint8Array) return new Blob([source])
  throw Object.assign(new Error('图片预览源无效'), { code: 'PREVIEW_SOURCE_INVALID' })
}
watch(() => props.source, () => {
  revoke()
  try { url.value = URL.createObjectURL(makeBlob(props.source)); emit('ready') } catch (error) { emit('error', error) }
}, { immediate: true })
onBeforeUnmount(revoke)
</script>
<style scoped>.image-viewer{height:100%;min-height:520px;overflow:auto;display:grid;place-items:start center;padding:18px;background:#eef2f7}.image-viewer img{max-width:100%;height:auto;background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.12)}</style>
