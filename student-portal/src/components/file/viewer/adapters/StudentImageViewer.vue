<script setup>
defineProps({ url: { type: String, required: true }, alt: { type: String, default: '图片文件' } })
</script>

<template><div class="student-image-viewer"><img :src="url" :alt="alt" /></div></template>

<style scoped>.student-image-viewer{min-height:65vh;display:grid;place-items:center;padding:24px;overflow:auto;background:#eef2f7}.student-image-viewer img{display:block;max-width:100%;max-height:78vh;object-fit:contain;box-shadow:0 8px 28px rgba(23,43,77,.15);background:#fff}</style>
