<template>
  <section class="aa-object-line" aria-label="当前排课事项">
    <strong class="aa-object-line__name">{{ name || '请选择排课事项' }}</strong>
    <span v-if="identity" class="aa-object-line__sub">{{ identity }}</span>
    <span v-if="status" class="aa-object-line__status">{{ status }}</span>
    <span class="aa-object-line__spacer" />
    <span v-if="owner" class="aa-object-line__meta"><em>办理人员</em>{{ owner }}</span>
    <span v-if="nextOwner" class="aa-object-line__meta"><em>后续办理</em>{{ nextOwner }}</span>
  </section>
</template>

<script setup>
// source 保留入参以兼容调用方，不再展示
defineProps({
  name: { type: String, default: '' },
  identity: { type: String, default: '' },
  source: { type: String, default: '' },
  status: { type: String, default: '' },
  owner: { type: String, default: '' },
  nextOwner: { type: String, default: '' }
})
</script>

<style scoped>
@import '../styles/object-line.css';
</style>
