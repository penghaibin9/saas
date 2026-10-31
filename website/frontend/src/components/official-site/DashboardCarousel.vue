<template>
  <section class="dashboard-carousel" role="region" aria-roledescription="轮播" aria-label="产品大屏展示" @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="pauseOnFocus" @keydown.left.prevent="step(-1)" @keydown.right.prevent="step(1)">
    <div class="dashboard-frame" :aria-live="paused ? 'polite' : 'off'" aria-atomic="true">
      <figure v-for="(slide, index) in slides" v-show="index === current" :key="slide.key" :aria-hidden="index !== current">
        <OfficialImageZoom :src="slide.src" :alt="`${slide.name} · 展示图，示例数据，非实时数据`" :caption="`${slide.name} · 示例数据，非实时数据`" :loading="index === current ? 'eager' : 'lazy'" />
      </figure>
    </div>
    <div class="carousel-controls"><button class="step-control" aria-label="上一张大屏" @click="step(-1)">‹</button><div class="slide-selectors" aria-label="选择大屏"><button v-for="(slide, index) in slides" :key="slide.key" :aria-pressed="current === index" @click="select(index)">{{ slide.name }}</button></div><button class="step-control" aria-label="下一张大屏" @click="step(1)">›</button><button class="play-control" :aria-label="paused ? '播放大屏轮播' : '暂停大屏轮播'" :aria-pressed="!paused" @click="paused = !paused">{{ paused ? '播放' : '暂停' }}</button></div>
    <p class="carousel-caption">大屏展示图 · 示例数据，非实时数据</p>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import OfficialImageZoom from './OfficialImageZoom.vue'
const slides = [
  { key: 'academic', name: '教务大屏' }, { key: 'affairs', name: '学工大屏' },
  { key: 'graduation', name: '毕业设计大屏' }, { key: 'internship', name: '岗位实习大屏' }
].map(slide => ({ ...slide, src: `/official-site/showcase-20260909/boards/${slide.key}.webp` }))
const current = ref(0), paused = ref(false), hovered = ref(false), hidden = ref(false)
const playing = computed(() => !paused.value && !hovered.value && !hidden.value)
let timer, stopWatching, motion
function select(index) { current.value = index; paused.value = true }
function step(delta) { select((current.value + delta + slides.length) % slides.length) }
function pauseOnFocus(event) { if (!event.target.closest('.play-control')) paused.value = true }
function updateVisibility() { hidden.value = document.hidden }
function updateMotion() { if (motion.matches) paused.value = true }
onMounted(() => {
  motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  updateMotion(); updateVisibility()
  motion.addEventListener('change', updateMotion)
  document.addEventListener('visibilitychange', updateVisibility)
  stopWatching = watch(playing, enabled => { clearInterval(timer); if (enabled) timer = setInterval(() => { current.value = (current.value + 1) % slides.length }, 8000) }, { immediate: true })
})
onBeforeUnmount(() => { clearInterval(timer); stopWatching?.(); motion?.removeEventListener('change', updateMotion); document.removeEventListener('visibilitychange', updateVisibility) })
</script>
<style scoped>
.dashboard-carousel{min-width:0;color:#d3e4f1}.dashboard-frame{aspect-ratio:1672/941;background:#071b30}.dashboard-frame figure{margin:0}.dashboard-frame :deep(.official-image-zoom){width:100%}.dashboard-frame :deep(img){display:block;width:100%;height:auto;object-fit:contain;border-radius:0}.dashboard-frame :deep(button){width:100%;padding:0;border:0;background:transparent}.carousel-controls{display:flex;align-items:center;justify-content:center;gap:14px;margin-top:12px}.carousel-controls button{font:inherit;cursor:pointer;color:#b9cedf;border:0;background:transparent;padding:8px 4px;min-height:44px;font-size:13px}.slide-selectors{display:flex;justify-content:center;gap:24px}.slide-selectors button{border-bottom:2px solid transparent}.slide-selectors button[aria-pressed=true]{color:#fff;border-bottom-color:#71cfff}.step-control{font-size:26px!important;min-width:44px}.play-control{min-width:44px}.carousel-controls button:hover{color:#fff}.carousel-caption{margin:4px 0 0;text-align:right;font-size:12px;color:#98b2c8;line-height:1.6}@media(max-width:1100px){.slide-selectors{gap:12px}.carousel-controls{gap:8px}}@media(max-width:600px){.carousel-controls{gap:4px;flex-wrap:wrap}.slide-selectors{gap:10px;order:-1;flex-basis:100%;justify-content:space-between}.carousel-controls button{font-size:12px}.carousel-caption{text-align:left;margin-top:6px}}
</style>
