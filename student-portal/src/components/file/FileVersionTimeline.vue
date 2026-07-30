<script setup>
defineProps({ items: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])
</script>

<template>
  <section class="student-file-timeline">
    <p v-if="!items.length">暂无历史版本</p>
    <button v-for="item in items" v-else :key="item.bindingId || `${item.file?.fileId}-${item.versionNo}`" type="button" @click="emit('select', item)">
      <span>版本 {{ item.versionNo }}<em v-if="item.isCurrent">当前</em></span>
      <strong>{{ item.file?.fileName || '未命名文件' }}</strong>
      <small>{{ item.file?.statusText || '状态未知' }} · {{ item.boundAt || '-' }}</small>
    </button>
  </section>
</template>

<style scoped>
.student-file-timeline { display: grid; gap: 10px; }
.student-file-timeline > button { display: grid; gap: 5px; padding: 13px 15px; border: 1px solid #e1e8f2; border-radius: 10px; background: #fff; text-align: left; cursor: pointer; }
.student-file-timeline span { display: flex; align-items: center; gap: 8px; color: #1769e0; }
.student-file-timeline em { padding: 1px 7px; border-radius: 999px; background: #e8f2ff; font-size: 12px; font-style: normal; }
.student-file-timeline small, .student-file-timeline p { color: #79869a; }
</style>
