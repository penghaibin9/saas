<template>
  <div v-if="versions.length" class="dv-version-bar">
    <span class="dv-version-bar__label">业务版本</span>
    <button
      v-for="item in versions"
      :key="String(item.fileVersionId ?? item.versionId ?? item.id)"
      type="button"
      :class="{ 'is-active': String(versionKey(item)) === String(activeVersionId) }"
      @click="$emit('select', item)"
    >
      v{{ item.versionNo ?? item.version ?? '—' }}
      <small v-if="String(versionKey(item)) !== String(canonicalVersionId)">历史只读</small>
      <small v-else>本次审核</small>
    </button>
  </div>
</template>
<script setup>
defineProps({ versions: { type: Array, default: () => [] }, activeVersionId: { type: [String, Number], default: null }, canonicalVersionId: { type: [String, Number], default: null } })
defineEmits(['select'])
const versionKey = (item) => item?.fileVersionId ?? item?.versionId ?? item?.id
</script>
<style scoped>
.dv-version-bar{display:flex;align-items:center;gap:7px;padding:8px 10px;border-bottom:1px solid var(--border-light);overflow:auto;background:var(--gray-50,#f8fafc)}.dv-version-bar__label{font-size:12px;color:var(--text-tertiary);white-space:nowrap}.dv-version-bar button{display:flex;gap:5px;align-items:center;border:1px solid var(--border-light);background:var(--card,#fff);border-radius:999px;padding:5px 9px;white-space:nowrap;cursor:pointer}.dv-version-bar button.is-active{border-color:var(--brand-primary,#2563eb);color:var(--brand-primary,#2563eb)}.dv-version-bar small{font-size:10px;color:var(--text-tertiary)}
</style>
