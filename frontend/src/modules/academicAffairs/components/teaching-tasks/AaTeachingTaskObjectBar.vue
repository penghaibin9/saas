<template>
  <section class="aa-object-line" aria-label="当前教学任务对象">
    <strong class="aa-object-line__name">{{ name || '当前教学任务' }}</strong>
    <span v-if="status" class="aa-object-line__status">{{ status }}</span>
    <span class="aa-object-line__spacer" />
    <span v-if="owner" class="aa-object-line__meta"><em>当前责任</em>{{ owner }}</span>
    <span v-if="nextOwner" class="aa-object-line__meta"><em>下一责任</em>{{ nextOwner }}</span>
  </section>
</template>

<script setup>
// identity、source 保留入参以兼容调用方，不再展示内部编号和来源说明
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
@import '../../styles/object-line.css';
</style>
