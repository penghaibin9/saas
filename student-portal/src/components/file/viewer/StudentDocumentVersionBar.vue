<script setup>
const props = defineProps({
  items: { type: Array, default: () => [] },
  activeFile: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['select'])

function key(item = {}) { return String(item.fileVersionId || item.versionId || item.fileId || '') }
function active(item) { return key(item) && key(item) === key(props.activeFile) }
</script>

<template>
  <nav v-if="items.length > 1" class="student-reader-versions" aria-label="文件版本">
    <span>版本</span>
    <button v-for="item in items" :key="key(item)" type="button" :class="{ active: active(item) }" @click="emit('select', item)">
      v{{ item.versionNo || '?' }}{{ item.isCurrent === false ? ' · 历史' : item.isCurrent ? ' · 当前' : '' }}
    </button>
  </nav>
</template>

<style scoped>
.student-reader-versions{display:flex;align-items:center;gap:8px;overflow:auto;padding:9px 14px;border-bottom:1px solid #e4eaf2;background:#f8fafc}.student-reader-versions>span{color:#7a8799;font-size:12px;flex:none}.student-reader-versions button{flex:none;min-height:30px;padding:0 10px;border:1px solid #d7e0ec;border-radius:999px;background:#fff;color:#4b5b72;cursor:pointer}.student-reader-versions button.active{border-color:#1769e0;background:#eaf3ff;color:#1769e0;font-weight:600}
</style>
