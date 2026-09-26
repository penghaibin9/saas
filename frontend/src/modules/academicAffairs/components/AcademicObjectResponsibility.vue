<template>
  <dl v-if="objectId" class="academic-object-responsibility" :data-object-id="objectId" aria-label="当前对象责任接力">
    <div><dt>当前责任</dt><dd>{{ owner }}</dd></div>
    <div><dt>下一责任岗位</dt><dd>{{ nextOwner }}</dd></div>
  </dl>
</template>

<script>
import { academicFlowOwner, academicFlowNextOwner } from '../config/academicFlowRegistry.js'
export default {
  name: 'AcademicObjectResponsibility',
  props: { objectId: { type: String, required: true }, responsibility: { type: Object, default: null }, nextStep: { type: Object, default: null } },
  computed: {
    owner() { return academicFlowOwner(this.responsibility) },
    nextOwner() { return academicFlowNextOwner(this.nextStep) }
  }
}
</script>

<style scoped>
.academic-object-responsibility { display:grid; gap:10px; margin:0; min-width:160px; font-size:12px; line-height:1.6; overflow-wrap:anywhere; }
.academic-object-responsibility dt { color:var(--text-secondary); }.academic-object-responsibility dd { margin:3px 0 0; color:var(--text-primary); }
</style>
