<template>
  <div ref="root" class="pdf-viewer" data-preview-adapter="pdf">
    <div v-for="n in pages" :key="n" class="pdf-page" :data-page="n">
      <canvas :ref="(el) => setCanvas(n, el)" :aria-label="`第 ${n} 页`"></canvas>
      <span class="pdf-page__number">{{ n }}</span>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import * as pdfjsLib from 'pdfjs-dist/build/pdf.mjs'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

const props = defineProps({
  source: { type: [Blob, ArrayBuffer, Uint8Array], required: true },
  generation: { type: Number, required: true },
  page: { type: Number, default: 1 },
  zoom: { type: Number, default: 1 }
})
const emit = defineEmits(['ready', 'page-change', 'error'])
const root = ref(null)
const pages = ref([])
const canvases = new Map()
const renderTasks = new Map()
let pdfDoc = null
let observer = null
let loadToken = 0

function setCanvas(page, el) { if (el) canvases.set(page, el); else canvases.delete(page) }

async function bytesFrom(source) {
  if (source instanceof Uint8Array) return source
  if (source instanceof ArrayBuffer) return new Uint8Array(source)
  if (source instanceof Blob) return new Uint8Array(await source.arrayBuffer())
  throw Object.assign(new Error('PDF 预览源必须是 Blob 或 ArrayBuffer'), { code: 'PREVIEW_SOURCE_INVALID' })
}

function cancelRenderTasks() {
  for (const task of renderTasks.values()) { try { task.cancel() } catch { /* PDF.js render task may already be complete */ } }
  renderTasks.clear()
}

async function destroyPdf() {
  cancelRenderTasks()
  observer?.disconnect()
  observer = null
  const doc = pdfDoc
  pdfDoc = null
  if (doc) { try { await doc.destroy() } catch { /* best-effort worker cleanup */ } }
}

async function renderPage(pageNo) {
  if (!pdfDoc || pageNo < 1 || pageNo > pdfDoc.numPages) return
  const canvas = canvases.get(pageNo)
  if (!canvas || canvas.dataset.zoom === String(props.zoom) || renderTasks.has(pageNo)) return
  const token = loadToken
  try {
    const page = await pdfDoc.getPage(pageNo)
    if (token !== loadToken || !pdfDoc) return
    const viewport = page.getViewport({ scale: props.zoom })
    const outputScale = Math.min(globalThis.devicePixelRatio || 1, 2)
    const context = canvas.getContext('2d', { alpha: false })
    canvas.width = Math.max(1, Math.floor(viewport.width * outputScale))
    canvas.height = Math.max(1, Math.floor(viewport.height * outputScale))
    canvas.style.width = `${Math.floor(viewport.width)}px`
    canvas.style.height = `${Math.floor(viewport.height)}px`
    const task = page.render({ canvasContext: context, viewport, transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0] })
    renderTasks.set(pageNo, task)
    await task.promise
    if (token === loadToken) canvas.dataset.zoom = String(props.zoom)
  } catch (error) {
    if (error?.name !== 'RenderingCancelledException') emit('error', error)
  } finally {
    renderTasks.delete(pageNo)
  }
}

function observePages() {
  observer?.disconnect()
  observer = new IntersectionObserver((entries) => {
    const visible = []
    for (const entry of entries) {
      const pageNo = Number(entry.target.dataset.page || 0)
      if (entry.isIntersecting) {
        visible.push({ pageNo, ratio: entry.intersectionRatio })
        for (let n = Math.max(1, pageNo - 2); n <= Math.min(pages.value.length, pageNo + 2); n++) renderPage(n)
      }
    }
    visible.sort((a, b) => b.ratio - a.ratio)
    if (visible[0]?.pageNo) emit('page-change', visible[0].pageNo)
  }, { root: root.value, rootMargin: '900px 0px', threshold: [0.01, 0.25, 0.6] })
  root.value?.querySelectorAll('.pdf-page').forEach((el) => observer.observe(el))
}

async function loadPdf() {
  const token = ++loadToken
  await destroyPdf()
  try {
    const data = await bytesFrom(props.source)
    if (token !== loadToken) return
    const task = pdfjsLib.getDocument({ data, isEvalSupported: false })
    const doc = await task.promise
    if (token !== loadToken) { await doc.destroy(); return }
    pdfDoc = doc
    pages.value = Array.from({ length: doc.numPages }, (_, i) => i + 1)
    await nextTick()
    observePages()
    emit('ready', { pageCount: doc.numPages })
    renderPage(Math.min(Math.max(props.page, 1), doc.numPages))
  } catch (error) {
    if (token === loadToken) emit('error', error)
  }
}

function goToPage(value) {
  const pageNo = Math.min(Math.max(Number(value) || 1, 1), pages.value.length || 1)
  const node = root.value?.querySelector(`[data-page="${pageNo}"]`)
  node?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  for (let n = Math.max(1, pageNo - 2); n <= Math.min(pages.value.length, pageNo + 2); n++) renderPage(n)
}

watch(() => [props.source, props.generation], loadPdf, { immediate: true })
watch(() => props.page, goToPage)
watch(() => props.zoom, async () => {
  cancelRenderTasks()
  for (const canvas of canvases.values()) delete canvas.dataset.zoom
  await nextTick()
  goToPage(props.page)
})
onBeforeUnmount(() => { loadToken += 1; destroyPdf() })
defineExpose({ goToPage })
</script>

<style scoped>
.pdf-viewer{height:100%;min-height:520px;overflow:auto;padding:18px;background:#e8edf3;scroll-behavior:smooth}.pdf-page{position:relative;min-height:640px;margin:0 auto 18px;width:max-content;max-width:100%;background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.12);display:flex;align-items:flex-start;justify-content:center}.pdf-page canvas{display:block;max-width:100%;height:auto}.pdf-page__number{position:absolute;right:8px;bottom:6px;padding:2px 6px;border-radius:999px;background:rgba(15,23,42,.64);color:#fff;font-size:11px;pointer-events:none}
</style>
