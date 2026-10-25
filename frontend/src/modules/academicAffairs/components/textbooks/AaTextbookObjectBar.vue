<template>
  <section class="aa-object-line" aria-label="当前教材业务对象">
    <strong class="aa-object-line__name">{{ title }}</strong>
    <span class="aa-object-line__sub">{{ objectType }}<template v-if="termName"> · {{ termName }}</template></span>
    <span class="aa-object-line__status">{{ statusLabel }}</span>
    <span class="aa-object-line__spacer" />
    <span class="aa-object-line__meta"><em>当前责任</em>{{ currentOwner }}</span>
    <span class="aa-object-line__meta"><em>下一责任</em>{{ nextOwner }}</span>
  </section>
</template>

<script>
// objectId、source 保留入参以兼容调用方，不再展示
export default {
  name: 'AaTextbookObjectBar',
  props: {
    title: { type: String, required: true },
    objectType: { type: String, required: true },
    objectId: { type: [String, Number], default: '' },
    termName: { type: String, default: '' },
    source: { type: String, required: true },
    statusLabel: { type: String, required: true },
    currentOwner: { type: String, required: true },
    nextOwner: { type: String, required: true }
  }
}
</script>

<style scoped>
@import '../../styles/object-line.css';
</style>
