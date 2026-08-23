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
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs'
import pdfWorkerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'
import {
  PDF_PREVIEW_MAX_CANVAS_DIMENSION,
  PDF_PREVIEW_MAX_CANVAS_PIXELS,
  PDF_PREVIEW_MAX_PAGES,
  PDF_PREVIEW_MAX_SOURCE_BYTES
} from '../viewer-contract'

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
const renderReservations = new Map()
let renderReservationSeq = 0
let pdfDoc = null
let observer = null
let loadToken = 0

function previewError(code, message) {
  return Object.assign(new Error(message), { code, retryable: false })
}

function setCanvas(page, el) { if (el) canvases.set(page, el); else canvases.delete(page) }

async function bytesFrom(source) {
  let data
  if (source instanceof Uint8Array) data = source
  else if (source instanceof ArrayBuffer) data = new Uint8Array(source)
  else if (source instanceof Blob) {
    if (source.size > PDF_PREVIEW_MAX_SOURCE_BYTES) throw previewError('PREVIEW_TOO_LARGE', 'PDF 超过 50MB 站内阅读上限，请下载原文查看')
    data = new Uint8Array(await source.arrayBuffer())
  } else throw previewError('PREVIEW_SOURCE_INVALID', 'PDF 预览源必须是 Blob 或 ArrayBuffer')
  if (data.byteLength > PDF_PREVIEW_MAX_SOURCE_BYTES) throw previewError('PREVIEW_TOO_LARGE', 'PDF 超过 50MB 站内阅读上限，请下载原文查看')
  return data
}

function cancelRenderTasks() {
  for (const task of renderTasks.values()) { try { task.cancel() } catch { /* PDF.js render task may already be complete */ } }
  renderTasks.clear()
  renderReservations.clear()
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
  if (!canvas || canvas.dataset.previewBlocked === 'true' || canvas.dataset.zoom === String(props.zoom) || renderReservations.has(pageNo)) return
  const token = loadToken
  const reservation = ++renderReservationSeq
  renderReservations.set(pageNo, reservation)
  let task = null
  try {
    const page = await pdfDoc.getPage(pageNo)
    if (token !== loadToken || !pdfDoc || renderReservations.get(pageNo) !== reservation) return
    const viewport = page.getViewport({ scale: props.zoom })
    const outputScale = Math.min(globalThis.devicePixelRatio || 1, 2)
    const pixelWidth = Math.max(1, Math.ceil(viewport.width * outputScale))
    const pixelHeight = Math.max(1, Math.ceil(viewport.height * outputScale))
    if (
      !Number.isFinite(pixelWidth) || !Number.isFinite(pixelHeight)
      || pixelWidth > PDF_PREVIEW_MAX_CANVAS_DIMENSION
      || pixelHeight > PDF_PREVIEW_MAX_CANVAS_DIMENSION
      || pixelWidth * pixelHeight > PDF_PREVIEW_MAX_CANVAS_PIXELS
    ) {
      canvas.dataset.previewBlocked = 'true'
      throw previewError('PREVIEW_TOO_COMPLEX', 'PDF 单页解码像素超过安全预览上限，请下载原文查看')
    }
    const context = canvas.getContext('2d', { alpha: false })
    canvas.width = pixelWidth
    canvas.height = pixelHeight
    canvas.style.width = `${Math.floor(viewport.width)}px`
    canvas.style.height = `${Math.floor(viewport.height)}px`
    task = page.render({ canvasContext: context, viewport, transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0] })
    renderTasks.set(pageNo, task)
    await task.promise
    if (token === loadToken && renderReservations.get(pageNo) === reservation) canvas.dataset.zoom = String(props.zoom)
  } catch (error) {
    if (
      error?.name !== 'RenderingCancelledException' &&
      token === loadToken &&
      renderReservations.get(pageNo) === reservation
    ) emit('error', error)
  } finally {
    if (task && renderTasks.get(pageNo) === task) renderTasks.delete(pageNo)
    if (renderReservations.get(pageNo) === reservation) renderReservations.delete(pageNo)
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
  }, {
    // Use the browser viewport as the observer root. IntersectionObserver still clips through
    // overflow ancestors, while an auto-height viewer cannot accidentally make every page
    // intersect at once and eagerly render an entire long document.
    root: null,
    rootMargin: '900px 0px',
    threshold: [0.01, 0.25, 0.6]
  })
  root.value?.querySelectorAll('.pdf-page').forEach((el) => observer.observe(el))
}

function resetInitialPosition(pageNo) {
  const viewer = root.value
  if (!viewer) return
  // A long document can leave both this scroller and the browser viewport anchored near its
  // tail. Reset the local scroller, then synchronously align the new generation's canonical page
  // before IntersectionObserver is attached. Otherwise a stale visible page can win the first
  // observer callback and overwrite page=1.
  const previousScrollBehavior = viewer.style.scrollBehavior
  viewer.style.scrollBehavior = 'auto'
  viewer.scrollTop = 0
  viewer.scrollLeft = 0
  const target = viewer.querySelector(`[data-page="${pageNo}"]`)
  target?.scrollIntoView({ block: 'start', behavior: 'auto' })
  viewer.style.scrollBehavior = previousScrollBehavior
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
    if (doc.numPages > PDF_PREVIEW_MAX_PAGES) {
      await doc.destroy()
      throw previewError('PREVIEW_TOO_COMPLEX', `PDF 超过 ${PDF_PREVIEW_MAX_PAGES} 页站内阅读上限，请下载原文查看`)
    }
    pdfDoc = doc
    pages.value = Array.from({ length: doc.numPages }, (_, i) => i + 1)
    await nextTick()
    const initialPage = Math.min(Math.max(Number(props.page) || 1, 1), doc.numPages)
    resetInitialPosition(initialPage)
    observePages()
    emit('ready', { pageCount: doc.numPages })
    renderPage(initialPage)
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
  for (const canvas of canvases.values()) {
    delete canvas.dataset.zoom
    delete canvas.dataset.previewBlocked
  }
  await nextTick()
  goToPage(props.page)
})
onBeforeUnmount(() => { loadToken += 1; destroyPdf() })
defineExpose({ goToPage })
</script>

<style scoped>
.pdf-viewer{height:100%;min-height:520px;overflow:auto;padding:18px;background:#e8edf3;scroll-behavior:smooth}.pdf-page{position:relative;min-height:640px;margin:0 auto 18px;width:max-content;max-width:100%;background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.12);display:flex;align-items:flex-start;justify-content:center}.pdf-page canvas{display:block;max-width:100%;height:auto}.pdf-page__number{position:absolute;right:8px;bottom:6px;padding:2px 6px;border-radius:999px;background:rgba(15,23,42,.64);color:#fff;font-size:11px;pointer-events:none}
</style>
