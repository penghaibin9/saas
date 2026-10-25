<template>
  <div v-if="objectId && compact" class="academic-object-responsibility is-compact" :data-object-id="objectId" :title="`当前责任：${owner}\n下一步：${nextOwner}`">
    <div class="academic-object-responsibility__owner">{{ shortOwner }}</div>
    <div class="academic-object-responsibility__next">下一步：{{ shortNext }}</div>
  </div>
  <dl v-else-if="objectId" class="academic-object-responsibility" :data-object-id="objectId" aria-label="当前对象责任接力">
    <div><dt>当前责任</dt><dd>{{ owner }}</dd></div>
    <div><dt>下一责任岗位</dt><dd>{{ nextOwner }}</dd></div>
  </dl>
</template>

<script>
import { academicFlowOwner, academicFlowNextOwner, academicFlowResponsibility } from '../config/academicFlowRegistry.js'
export default {
  name: 'AcademicObjectResponsibility',
  // compact：列表单元格用，只显示组织和责任人一行、下一步一行，完整信息在悬停提示里
  props: { objectId: { type: String, required: true }, responsibility: { type: Object, default: null }, nextStep: { type: Object, default: null }, compact: { type: Boolean, default: false } },
  computed: {
    shortOwner() {
      const display = academicFlowResponsibility(this.responsibility)
      return [display.orgName, display.resolved ? display.assigneeLabel : display.positionLabel].filter(Boolean).join(' · ')
    },
    shortNext() { return academicFlowNextOwner(this.nextStep ? { label: this.nextStep.label } : null) },
    owner() { return academicFlowOwner(this.responsibility) },
    nextOwner() { return academicFlowNextOwner(this.nextStep) }
  }
}
</script>

<style scoped>
.academic-object-responsibility { display:grid; gap:10px; margin:0; min-width:160px; font-size:12px; line-height:1.6; overflow-wrap:anywhere; }
.academic-object-responsibility dt { color:var(--text-secondary); }.academic-object-responsibility dd { margin:3px 0 0; color:var(--text-primary); }
.academic-object-responsibility.is-compact { display:block; min-width:140px; }
.academic-object-responsibility__owner { color:var(--text-primary); font-size:13px; }
.academic-object-responsibility__next { margin-top:2px; color:var(--text-secondary); font-size:12px; }
</style>
