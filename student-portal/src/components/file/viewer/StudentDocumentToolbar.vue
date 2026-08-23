<script setup>
defineProps({
  file: { type: Object, default: () => ({}) },
  readOnly: { type: Boolean, default: false },
  canDownload: { type: Boolean, default: false }
})
const emit = defineEmits(['download', 'close'])
</script>

<template>
  <header class="student-reader-toolbar">
    <div class="student-reader-toolbar__title">
      <strong>{{ file.fileName || '未命名文件' }}</strong>
      <span v-if="file.versionNo">v{{ file.versionNo }}</span>
      <span v-if="readOnly" class="is-history">历史版本 · 只读</span>
      <span v-else class="is-current">当前版本</span>
    </div>
    <nav>
      <button v-if="canDownload" type="button" @click="emit('download')">下载</button>
      <button type="button" class="is-close" @click="emit('close')">关闭阅读器</button>
    </nav>
  </header>
</template>

<style scoped>
.student-reader-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 16px;border-bottom:1px solid #e4eaf2;background:#fff}.student-reader-toolbar__title{min-width:0;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.student-reader-toolbar strong{max-width:min(52vw,680px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.student-reader-toolbar span{padding:2px 7px;border-radius:999px;background:#eef3f9;color:#637086;font-size:12px}.student-reader-toolbar .is-current{background:#e9f8ef;color:#16794a}.student-reader-toolbar .is-history{background:#fff3db;color:#915c00}.student-reader-toolbar nav{display:flex;gap:8px;flex:none}.student-reader-toolbar button{min-height:34px;padding:0 12px;border:1px solid #cbd8e8;border-radius:8px;background:#fff;color:#1769e0;cursor:pointer}.student-reader-toolbar button.is-close{color:#344054}@media(max-width:720px){.student-reader-toolbar{align-items:flex-start}.student-reader-toolbar strong{max-width:55vw}.student-reader-toolbar nav{display:grid}}
</style>
