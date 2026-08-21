<template>
  <div class="dv-toolbar">
    <div class="dv-toolbar__group">
      <template v-if="showPageNavigation">
        <button type="button" :disabled="page <= 1" @click="$emit('page', page - 1)">上一页</button>
        <span>{{ page }} / {{ pageCount || '—' }}</span>
        <button type="button" :disabled="!pageCount || page >= pageCount" @click="$emit('page', page + 1)">下一页</button>
      </template>
      <span v-else>连续阅读</span>
    </div>
    <div class="dv-toolbar__group">
      <button type="button" :disabled="zoom <= 0.6" @click="$emit('zoom', Math.max(0.6, zoom - 0.1))">−</button>
      <span>{{ Math.round(zoom * 100) }}%</span>
      <button type="button" :disabled="zoom >= 2.4" @click="$emit('zoom', Math.min(2.4, zoom + 0.1))">＋</button>
      <button type="button" @click="$emit('fullscreen')">{{ fullscreen ? '退出全屏' : '全屏阅读' }}</button>
      <button v-if="allowDownload" type="button" @click="$emit('download')">下载原文</button>
    </div>
  </div>
</template>
<script setup>
defineProps({
  page: { type: Number, default: 1 }, pageCount: { type: Number, default: 0 }, zoom: { type: Number, default: 1 },
  fullscreen: { type: Boolean, default: false }, allowDownload: { type: Boolean, default: false },
  showPageNavigation: { type: Boolean, default: true }
})
defineEmits(['page', 'zoom', 'fullscreen', 'download'])
</script>
<style scoped>
.dv-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--border-light);background:var(--card,#fff);position:sticky;top:0;z-index:5}.dv-toolbar__group{display:flex;align-items:center;gap:6px}.dv-toolbar button{padding:5px 9px;border:1px solid var(--border-light);border-radius:7px;background:var(--card,#fff);color:var(--text-secondary);cursor:pointer}.dv-toolbar button:disabled{opacity:.4;cursor:not-allowed}
</style>
