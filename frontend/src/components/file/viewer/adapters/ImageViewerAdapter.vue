<template><div class="image-viewer" data-preview-adapter="image"><img v-if="url" :src="url" :alt="fileName || '文件图片预览'" /></div></template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { IMAGE_PREVIEW_MAX_PIXELS, IMAGE_PREVIEW_MAX_SOURCE_BYTES } from '../viewer-contract'
import { detectImageDimensions } from './image-dimensions'

const props = defineProps({
  source: { type: [Blob, ArrayBuffer, Uint8Array], required: true },
  fileName: { type: String, default: '' },
  generation: { type: Number, default: 0 }
})
const emit = defineEmits(['ready', 'error'])
const url = ref('')
let loadToken = 0

function previewError(code, message) {
  return Object.assign(new Error(message), { code, retryable: false })
}

function revoke() {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''
}

function makeBlob(source) {
  if (source instanceof Blob) return source
  if (source instanceof ArrayBuffer || source instanceof Uint8Array) return new Blob([source])
  throw previewError('PREVIEW_SOURCE_INVALID', '图片预览源无效')
}

async function loadImage() {
  const token = ++loadToken
  revoke()
  try {
    const blob = makeBlob(props.source)
    if (blob.size > IMAGE_PREVIEW_MAX_SOURCE_BYTES) throw previewError('PREVIEW_TOO_LARGE', '图片超过 20MB 站内阅读上限，请下载原图查看')
    const dimensions = detectImageDimensions(new Uint8Array(await blob.arrayBuffer()))
    if (token !== loadToken) return
    if (!dimensions) throw previewError('PREVIEW_IMAGE_MALFORMED', '图片尺寸无法安全解析，请下载原图查看')
    if (dimensions.pixels > IMAGE_PREVIEW_MAX_PIXELS) throw previewError('PREVIEW_TOO_COMPLEX', '图片解码像素超过安全预览上限，请下载原图查看')
    url.value = URL.createObjectURL(blob)
    emit('ready', { width: dimensions.width, height: dimensions.height })
  } catch (error) {
    if (token !== loadToken) return
    emit('error', error)
  }
}

watch(() => [props.source, props.generation], loadImage, { immediate: true })
onBeforeUnmount(() => { loadToken += 1; revoke() })
</script>
<style scoped>.image-viewer{height:100%;min-height:520px;overflow:auto;display:grid;place-items:start center;padding:18px;background:#eef2f7}.image-viewer img{max-width:100%;height:auto;background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.12)}</style>
