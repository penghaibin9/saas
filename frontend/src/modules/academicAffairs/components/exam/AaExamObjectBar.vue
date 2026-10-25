<template>
  <section class="aa-object-line aeob" aria-label="当前考务业务对象">
    <strong class="aa-object-line__name">{{ title || '等待选择考务对象' }}</strong>
    <span v-if="status" class="aa-object-line__status">{{ status }}</span>
    <span class="aa-object-line__spacer" />
    <span v-if="owner" class="aa-object-line__meta"><em>当前责任人</em>{{ owner }}</span>
    <span v-if="blocked && blocker" class="aa-object-line__meta is-risk"><em>当前阻断</em>{{ blocker }}</span>
    <span v-if="nextOwner" class="aa-object-line__meta"><em>下一责任岗位</em>{{ nextOwner }}</span>
  </section>
</template>

<script>
// objectId、source 保留入参以兼容调用方，不再展示内部编号和来源说明
export default {
  name: 'AaExamObjectBar',
  props: {
    title: { type: String, default: '' }, objectId: { type: String, default: '' },
    source: { type: String, default: '' }, status: { type: String, default: '' },
    owner: { type: String, default: '' }, blocker: { type: String, default: '' },
    nextOwner: { type: String, default: '' }, blocked: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
@import '../../styles/object-line.css';
.aeob { margin-bottom: 12px; }
</style>
