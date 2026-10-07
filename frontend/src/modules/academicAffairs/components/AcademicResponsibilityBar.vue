<template>
  <section class="academic-responsibility" :class="{ 'is-unresolved': !display.resolved }" aria-label="当前责任">
    <div><small>{{ title }}</small><strong>{{ display.orgName }}</strong></div>
    <div><small>责任岗位</small><span>{{ display.positionLabel }}</span></div>
    <div><small>责任人</small><span>{{ display.assigneeLabel }}</span></div>
    <p v-if="display.reason" role="status">{{ display.reason }}</p>
  </section>
</template>

<script>
import { academicFlowResponsibility } from '../config/academicFlowRegistry.js'
export default {
  name: 'AcademicResponsibilityBar',
  props: { responsibility: { type: Object, default: null }, title: { type: String, default: '当前责任组织' } },
  computed: { display() { return academicFlowResponsibility(this.responsibility) } }
}
</script>

<style scoped>
.academic-responsibility { display:flex; align-items:start; flex-wrap:wrap; gap:12px 24px; padding:12px 14px; border:1px solid var(--border-base); border-radius:8px; background:var(--bg-soft,var(--bg-card)); font-size:13px; line-height:1.6; overflow-wrap:anywhere; }
.academic-responsibility > div { display:grid; gap:3px; min-width:120px; flex:1; }.academic-responsibility small { color:var(--text-secondary); font-size:12px; }.academic-responsibility p { flex-basis:100%; margin:0; color:var(--warning-color,#9a600f); }.is-unresolved { border-color:var(--warning-border,#e7d8b9); }
</style>
