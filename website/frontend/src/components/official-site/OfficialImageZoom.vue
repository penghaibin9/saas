<template>
  <button class="yk-image-zoom" type="button" :aria-label="`放大查看：${alt}`" @click="open = true">
    <img :src="src" :alt="alt" :width="dimensions.width" :height="dimensions.height" :loading="loading" :fetchpriority="loading === 'eager' ? 'high' : 'auto'" decoding="async" />
    <span aria-hidden="true">放大查看</span>
  </button>
  <Teleport v-if="open" to="body">
    <div ref="dialog" class="yk-image-lightbox" role="dialog" aria-modal="true" :aria-label="alt">
      <div class="zoom-toolbar"><div class="zoom-heading"><strong>{{ caption || alt }}</strong><small>放大后可横向、纵向滑动查看</small></div><div class="zoom-actions">
        <button type="button" aria-label="缩小图片" :disabled="zoom <= 1 || imageError" @click="setZoom(zoom - .5)">−</button>
        <output aria-live="polite" aria-label="图片缩放比例">{{ Math.round(zoom * 100) }}%</output>
        <button type="button" aria-label="放大图片" :disabled="zoom >= 4 || imageError" @click="setZoom(zoom + .5)">＋</button>
        <button type="button" @click="setZoom(1)">适应屏幕</button><a :href="src" target="_blank" rel="noopener noreferrer">查看原图 ↗</a>
        <button ref="closeButton" type="button" aria-label="关闭图片预览" @click="open = false">关闭</button>
      </div></div>
      <div ref="viewport" class="zoom-viewport" tabindex="0" aria-label="大图查看区域，可使用方向键滚动">
        <p v-if="imageError" class="zoom-error" role="alert">图片暂时无法显示，请重新打开或查看原图。</p>
        <div v-else class="zoom-canvas" :style="{ width: fitWidth ? `${fitWidth * zoom + 32}px` : '100%' }"><img ref="image" :src="src" :alt="alt" :style="{ width: fitWidth ? `${fitWidth * zoom}px` : 'auto' }" @load="fitImage" @error="imageError = true" /></div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import sizes from '../../config/officialImageSizes.json'
export default {
  name: 'OfficialImageZoom',
  props: {
    src: { type: String, required: true },
    alt: { type: String, required: true },
    caption: { type: String, default: '' },
    loading: { type: String, default: 'lazy' }
  },
  computed: { dimensions() { return sizes[this.src.split('?')[0]] || {} } },
  data() { return { open: false, zoom: 1, fitWidth: 0, imageError: false } },
  watch: { open(value) {
    if (value) { this.zoom = 1; this.fitWidth = 0; this.imageError = false; this.opener = document.activeElement; this.previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden'; this.$nextTick(() => this.$refs.closeButton?.focus()) }
    else { document.body.style.overflow = this.previousOverflow || ''; if (this.opener?.isConnected) this.opener.focus({ preventScroll: true }) }
  } },
  mounted() { window.addEventListener('keydown', this.handleKeydown); window.addEventListener('resize', this.fitImage) },
  beforeUnmount() { window.removeEventListener('keydown', this.handleKeydown); window.removeEventListener('resize', this.fitImage); if (this.open) document.body.style.overflow = this.previousOverflow || '' },
  methods: {
    fitImage() {
      const image = this.$refs.image, viewport = this.$refs.viewport
      if (!this.open || !image?.naturalWidth || !viewport) return
      this.fitWidth = Math.max(1, Math.min(image.naturalWidth, viewport.clientWidth - 32, (viewport.clientHeight - 32) * image.naturalWidth / image.naturalHeight))
    },
    setZoom(value) {
      const next = Math.max(1, Math.min(4, value)), viewport = this.$refs.viewport
      if (!Number.isFinite(value) || !viewport) return
      const ratio = next / this.zoom
      const left = (viewport.scrollLeft + viewport.clientWidth / 2) * ratio - viewport.clientWidth / 2
      const top = (viewport.scrollTop + viewport.clientHeight / 2) * ratio - viewport.clientHeight / 2
      this.zoom = next
      this.$nextTick(() => { if (this.$refs.viewport === viewport) viewport.scrollTo(next === 1 ? 0 : left, next === 1 ? 0 : top) })
    },
    handleKeydown(event) {
      if (!this.open) return
      if (event.key === 'Escape') { event.preventDefault(); this.open = false }
      if (event.key !== 'Tab') return
      const controls = [...this.$refs.dialog.querySelectorAll('button:not([disabled]),a[href],[tabindex="0"]')]
      const first = controls[0], last = controls.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
  }
}
</script>

<style scoped>
.yk-image-zoom { position: relative; display: block; width: 100%; padding: 0; overflow: hidden; border: 0; background: transparent; cursor: zoom-in; text-align: inherit; }
.yk-image-zoom img { display: block; width: 100%; height: auto; }
.yk-image-zoom > span { position: absolute; right: 10px; bottom: 10px; padding: 6px 9px; border-radius: 999px; color: #fff; background: rgba(10, 31, 61, .78); font-size: 10px; font-weight: 800; opacity: 0; transform: translateY(4px); transition: opacity .18s ease, transform .18s ease; }
.yk-image-zoom:hover > span, .yk-image-zoom:focus-visible > span { opacity: 1; transform: translateY(0); }
.yk-image-lightbox { position:fixed;inset:0;z-index:1000;display:flex;flex-direction:column;padding:16px;gap:12px;background:#071725;color:#f2f7fc;font:14px/1.6 "Microsoft YaHei","PingFang SC",sans-serif;box-sizing:border-box }
.zoom-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.zoom-heading{min-width:0}.zoom-heading strong{display:block;font-size:16px}.zoom-heading small{display:block;color:#b5cadb;font-size:12px}.zoom-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.zoom-actions button,.zoom-actions a{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;padding:7px 12px;box-sizing:border-box;border:1px solid #58758d;border-radius:6px;background:#152e42;color:#fff;text-decoration:none;font:inherit;cursor:pointer}.zoom-actions button:disabled{opacity:.4;cursor:default}.zoom-actions output{min-width:48px;text-align:center;font-variant-numeric:tabular-nums}.zoom-actions button:focus-visible,.zoom-actions a:focus-visible,.zoom-viewport:focus-visible{outline:3px solid #84d9ff;outline-offset:2px}
.zoom-viewport{min-height:0;flex:1;overflow:auto;overscroll-behavior:contain;touch-action:pan-x pan-y;border:1px solid #284255;border-radius:8px;background:#04101b}.zoom-canvas{box-sizing:border-box;min-width:100%;min-height:100%;display:grid;place-items:center;padding:16px}.zoom-canvas img{display:block;max-width:none;height:auto;flex-shrink:0}.zoom-error{padding:24px;color:#fff}
@media(max-width:640px){.yk-image-lightbox{padding:10px;gap:10px}.zoom-toolbar{gap:8px}.zoom-heading strong{font-size:14px}.zoom-actions{gap:6px}.zoom-actions button,.zoom-actions a{padding:6px 9px;font-size:12px}.yk-image-zoom>span{opacity:1;transform:none;font-size:12px}}
</style>
