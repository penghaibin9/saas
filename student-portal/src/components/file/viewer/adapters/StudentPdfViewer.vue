<script setup>
defineProps({ url: { type: String, required: true }, title: { type: String, default: 'PDF 文件' } })
</script>

<template><iframe class="student-pdf-viewer" :src="url" :title="title" /></template>

<style scoped>.student-pdf-viewer{display:block;width:100%;height:100%;min-height:70vh;border:0;background:#e9eef5}</style>
