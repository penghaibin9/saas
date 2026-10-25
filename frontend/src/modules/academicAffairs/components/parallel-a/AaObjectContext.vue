<template>
  <section class="aa-object-line aa-a-object" aria-label="当前业务对象">
    <strong class="aa-object-line__name">{{ name }}</strong>
    <span v-if="identity" class="aa-object-line__sub">{{ identity }}</span>
    <span v-if="status" class="aa-object-line__status">{{ status }}</span>
    <span class="aa-object-line__spacer" />
    <span v-if="owner" class="aa-object-line__meta"><em>当前责任</em>{{ owner }}</span>
    <span v-if="nextStep" class="aa-object-line__meta"><em>下一步</em>{{ nextStep }}</span>
    <slot />
  </section>
</template>
<script setup>
// source 保留入参以兼容调用方；需要常显的提示由页面就近放置
defineProps({ name: { type: String, required: true }, identity: { type: String, default: '' }, source: { type: String, default: '' }, status: { type: String, default: '' }, owner: { type: String, default: '' }, nextStep: { type: String, default: '' } })
</script>
<style scoped>
@import '../../styles/object-line.css';
.aa-a-object { margin-bottom: 14px; }
</style>
