<script setup>
defineProps({ fileName: { type: String, default: '该文件' }, canDownload: { type: Boolean, default: false } })
const emit = defineEmits(['download'])
</script>

<template>
  <div class="student-unsupported-viewer">
    <strong>该格式暂不支持站内阅读</strong>
    <p>{{ fileName }} 不会自动下载或打开新标签页。</p>
    <button v-if="canDownload" type="button" @click="emit('download')">明确下载到本机</button>
  </div>
</template>

<style scoped>.student-unsupported-viewer{min-height:420px;display:grid;place-content:center;justify-items:center;gap:10px;padding:30px;text-align:center;background:#f7f9fc;color:#64748b}.student-unsupported-viewer strong{font-size:18px;color:#26364d}.student-unsupported-viewer p{margin:0}.student-unsupported-viewer button{margin-top:8px;padding:9px 14px;border:1px solid #cbd8e8;border-radius:8px;background:#fff;color:#1769e0;cursor:pointer}</style>
