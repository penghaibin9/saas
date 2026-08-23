<template>
  <button class="yk-image-zoom" type="button" :aria-label="`放大查看：${alt}`" @click="open = true">
    <img :src="src" :alt="alt" :loading="loading" decoding="async" />
    <span aria-hidden="true">放大查看</span>
  </button>
  <Teleport to="body">
    <div v-if="open" class="yk-image-lightbox" role="dialog" aria-modal="true" :aria-label="alt" @click.self="open = false">
      <button class="yk-image-lightbox-close" type="button" aria-label="关闭图片预览" @click="open = false">×</button>
      <figure><img :src="src" :alt="alt" /><figcaption v-if="caption">{{ caption }}</figcaption></figure>
    </div>
  </Teleport>
</template>

<script>
export default {
  name: 'OfficialImageZoom',
  props: {
    src: { type: String, required: true },
    alt: { type: String, required: true },
    caption: { type: String, default: '' },
    loading: { type: String, default: 'lazy' }
  },
  data() { return { open: false } },
  mounted() { window.addEventListener('keydown', this.handleKeydown) },
  beforeUnmount() { window.removeEventListener('keydown', this.handleKeydown) },
  methods: { handleKeydown(event) { if (event.key === 'Escape') this.open = false } }
}
</script>

<style scoped>
.yk-image-zoom { position: relative; display: block; width: 100%; padding: 0; overflow: hidden; border: 0; background: transparent; cursor: zoom-in; text-align: inherit; }
.yk-image-zoom img { display: block; width: 100%; }
.yk-image-zoom > span { position: absolute; right: 10px; bottom: 10px; padding: 6px 9px; border-radius: 999px; color: #fff; background: rgba(10, 31, 61, .78); font-size: 10px; font-weight: 800; opacity: 0; transform: translateY(4px); transition: opacity .18s ease, transform .18s ease; }
.yk-image-zoom:hover > span, .yk-image-zoom:focus-visible > span { opacity: 1; transform: translateY(0); }
.yk-image-lightbox { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 28px; background: rgba(5, 17, 34, .88); backdrop-filter: blur(8px); }
.yk-image-lightbox figure { max-width: min(1440px, 94vw); max-height: 90vh; margin: 0; overflow: auto; border-radius: 14px; background: #fff; box-shadow: 0 32px 90px rgba(0, 0, 0, .4); }
.yk-image-lightbox figure img { display: block; max-width: 100%; height: auto; }
.yk-image-lightbox figcaption { padding: 12px 16px; color: #53657c; font-size: 12px; }
.yk-image-lightbox-close { position: fixed; right: 22px; top: 18px; width: 42px; height: 42px; border: 1px solid rgba(255, 255, 255, .32); border-radius: 50%; color: #fff; background: rgba(255, 255, 255, .12); font-size: 26px; line-height: 1; cursor: pointer; }
@media (max-width: 640px) { .yk-image-lightbox { padding: 52px 10px 20px; } .yk-image-zoom > span { display: none; } }
</style>
