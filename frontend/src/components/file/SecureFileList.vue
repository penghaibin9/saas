<script setup>
const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无文件' }
})
const emit = defineEmits(['preview', 'download', 'refresh'])

function sizeText(value) {
  const size = Number(value || 0)
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <section class="secure-file-list">
    <header class="secure-file-list__header">
      <strong>安全文件</strong>
      <button type="button" @click="emit('refresh')">刷新</button>
    </header>
    <div v-if="loading" class="secure-file-list__state">正在加载文件…</div>
    <div v-else-if="!props.items.length" class="secure-file-list__state">{{ emptyText }}</div>
    <ul v-else class="secure-file-list__items">
      <li v-for="item in props.items" :key="item.fileId" class="secure-file-list__item">
        <div class="secure-file-list__main">
          <strong :title="item.fileName">{{ item.fileName || '未命名文件' }}</strong>
          <span>{{ sizeText(item.sizeBytes || item.size) }} · {{ item.statusText || '状态未知' }}</span>
        </div>
        <div class="secure-file-list__actions">
          <button v-if="item.canPreview" type="button" @click="emit('preview', item)">预览</button>
          <button v-if="item.canDownload" type="button" @click="emit('download', item)">下载</button>
          <span v-if="!item.canPreview && !item.canDownload" class="secure-file-list__locked">暂不可使用</span>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.secure-file-list { border: 1px solid #e2e8f2; border-radius: 12px; background: #fff; overflow: hidden; }
.secure-file-list__header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid #edf1f7; }
.secure-file-list__header button, .secure-file-list__actions button { border: 0; background: transparent; color: #1769e0; cursor: pointer; }
.secure-file-list__state { padding: 28px 16px; text-align: center; color: #7b8798; }
.secure-file-list__items { list-style: none; margin: 0; padding: 0; }
.secure-file-list__item { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border-bottom: 1px solid #edf1f7; }
.secure-file-list__item:last-child { border-bottom: 0; }
.secure-file-list__main { min-width: 0; display: grid; gap: 5px; }
.secure-file-list__main strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #24324a; }
.secure-file-list__main span, .secure-file-list__locked { color: #7b8798; font-size: 13px; }
.secure-file-list__actions { display: flex; align-items: center; gap: 8px; flex: none; }
</style>
