<template>
  <div v-if="files.length > 1" class="dv-file-switcher">
    <span>附件</span>
    <button v-for="item in files" :key="String(fileKey(item))" type="button" :class="{ 'is-active': String(fileKey(item)) === String(activeFileKey) }" @click="$emit('select', item)">{{ item.materialName || item.fileName || '附件' }}</button>
  </div>
</template>
<script setup>
defineProps({ files: { type: Array, default: () => [] }, activeFileKey: { type: [String, Number], default: null } })
defineEmits(['select'])
const fileKey = (item) => item?.fileKey ?? item?.fileVersionId ?? item?.versionId ?? item?.fileId
</script>
<style scoped>
.dv-file-switcher{display:flex;align-items:center;gap:7px;padding:7px 10px;border-bottom:1px solid var(--border-light);overflow:auto}.dv-file-switcher>span{font-size:12px;color:var(--text-tertiary)}.dv-file-switcher button{border:0;background:transparent;color:var(--text-secondary);padding:4px 7px;border-radius:6px;white-space:nowrap;cursor:pointer}.dv-file-switcher button.is-active{background:var(--primary-50,#eff6ff);color:var(--brand-primary,#2563eb);font-weight:600}
</style>
