<template>
  <div class="unsupported-viewer" data-preview-adapter="unsupported">
    <strong>当前格式暂不支持站内预览</strong>
    <p>系统不会自动下载或跳出当前批阅流程。</p>
    <button v-if="allowDownload" type="button" @click="$emit('download')">下载原文</button>
  </div>
</template>
<script setup>defineProps({ allowDownload: { type: Boolean, default: false } }); defineEmits(['download'])</script>
<style scoped>.unsupported-viewer{min-height:420px;display:grid;place-content:center;text-align:center;color:var(--text-secondary)}.unsupported-viewer strong{color:var(--text-primary)}.unsupported-viewer button{margin:12px auto 0;padding:7px 14px;border:1px solid var(--border-light);border-radius:8px;background:#fff;cursor:pointer}</style>
