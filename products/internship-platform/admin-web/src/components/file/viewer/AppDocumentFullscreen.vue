<template>
  <div ref="root" class="dv-fullscreen" :class="{ 'is-fullscreen': active }"><slot /></div>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ active: { type: Boolean, default: false } })
const emit = defineEmits(['update:active'])
const root = ref(null)
async function syncFullscreen(wanted) {
  if (!root.value || typeof document === 'undefined') return
  if (wanted && document.fullscreenElement !== root.value) {
    try { await root.value.requestFullscreen() } catch { emit('update:active', false) }
  } else if (!wanted && document.fullscreenElement === root.value) {
    try { await document.exitFullscreen() } catch { /* browser owns fullscreen teardown */ }
  }
}
function onChange() { emit('update:active', document.fullscreenElement === root.value) }
watch(() => props.active, syncFullscreen)
if (typeof document !== 'undefined') document.addEventListener('fullscreenchange', onChange)
onBeforeUnmount(() => { if (typeof document !== 'undefined') document.removeEventListener('fullscreenchange', onChange) })
</script>
<style scoped>
.dv-fullscreen{min-width:0;background:var(--gray-50,#f8fafc)}.dv-fullscreen.is-fullscreen{width:100vw;height:100vh;overflow:auto;background:#eef2f7}
</style>
