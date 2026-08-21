<script setup>
defineProps({ status: { type: String, default: 'idle' }, error: { type: String, default: '' } })
const emit = defineEmits(['retry'])
</script>

<template>
  <div class="student-reader-state">
    <template v-if="status === 'loading'"><strong>正在安全读取文件…</strong><p>文件内容仅在当前会话内存中打开，不生成公共直链。</p></template>
    <template v-else-if="status === 'error'"><strong>暂时无法预览</strong><p>{{ error || '请稍后重试' }}</p><button type="button" @click="emit('retry')">重新读取</button></template>
    <template v-else><strong>等待选择文件</strong></template>
  </div>
</template>

<style scoped>
.student-reader-state{min-height:360px;display:grid;place-content:center;justify-items:center;gap:8px;padding:30px;text-align:center;color:#65748a}.student-reader-state strong{color:#26364d}.student-reader-state p{max-width:520px;margin:0;line-height:1.6}.student-reader-state button{margin-top:6px;padding:8px 13px;border:1px solid #c9d7e8;border-radius:8px;background:#fff;color:#1769e0;cursor:pointer}
</style>
