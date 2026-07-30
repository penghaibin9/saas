<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  emptyText: { type: String, default: '暂无历史版本' }
})
const emit = defineEmits(['select'])
</script>

<template>
  <section class="file-version-timeline">
    <div v-if="!items.length" class="file-version-timeline__empty">{{ emptyText }}</div>
    <ol v-else>
      <li v-for="item in items" :key="item.bindingId || `${item.file?.fileId}-${item.versionNo}`">
        <span class="file-version-timeline__dot" />
        <button type="button" @click="emit('select', item)">
          <strong>版本 {{ item.versionNo }}</strong>
          <span>{{ item.file?.fileName || '未命名文件' }}</span>
          <small>{{ item.file?.statusText || '状态未知' }} · {{ item.boundAt || '-' }}</small>
        </button>
        <em v-if="item.isCurrent">当前</em>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.file-version-timeline ol { list-style: none; margin: 0; padding: 0 0 0 12px; }
.file-version-timeline li { position: relative; display: flex; align-items: flex-start; gap: 10px; padding: 0 0 18px 18px; border-left: 1px solid #dce5f2; }
.file-version-timeline li:last-child { padding-bottom: 0; }
.file-version-timeline__dot { position: absolute; left: -5px; top: 5px; width: 9px; height: 9px; border-radius: 50%; background: #1769e0; }
.file-version-timeline button { min-width: 0; display: grid; gap: 3px; padding: 0; border: 0; background: transparent; text-align: left; cursor: pointer; }
.file-version-timeline button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #40506a; }
.file-version-timeline button small { color: #7b8798; }
.file-version-timeline em { padding: 2px 8px; border-radius: 999px; background: #e8f2ff; color: #1769e0; font-size: 12px; font-style: normal; }
.file-version-timeline__empty { padding: 20px; text-align: center; color: #7b8798; }
</style>
