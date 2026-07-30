<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['preview', 'download', 'refresh'])
</script>

<template>
  <section class="student-file-list">
    <header><strong>我的文件</strong><button type="button" @click="emit('refresh')">刷新</button></header>
    <p v-if="loading" class="student-file-list__empty">正在加载…</p>
    <p v-else-if="!items.length" class="student-file-list__empty">暂无文件</p>
    <article v-for="item in items" v-else :key="item.fileId">
      <div>
        <strong>{{ item.fileName || '未命名文件' }}</strong>
        <small>{{ item.statusText || '状态未知' }}</small>
      </div>
      <nav>
        <button v-if="item.canPreview" type="button" @click="emit('preview', item)">查看</button>
        <button v-if="item.canDownload" type="button" @click="emit('download', item)">下载</button>
        <span v-if="!item.canPreview && !item.canDownload">暂不可使用</span>
      </nav>
    </article>
  </section>
</template>

<style scoped>
.student-file-list { overflow: hidden; border: 1px solid #e1e8f2; border-radius: 12px; background: #fff; }
.student-file-list header, .student-file-list article { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 16px; border-bottom: 1px solid #edf1f6; }
.student-file-list article:last-child { border-bottom: 0; }
.student-file-list article > div { min-width: 0; display: grid; gap: 5px; }
.student-file-list article strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.student-file-list small, .student-file-list nav span { color: #79869a; }
.student-file-list button { border: 0; background: transparent; color: #1769e0; cursor: pointer; }
.student-file-list nav { display: flex; gap: 8px; flex: none; }
.student-file-list__empty { margin: 0; padding: 24px 16px; text-align: center; color: #79869a; }
</style>
