<template>
  <article class="academic-school-gate">
    <header><h3>{{ title }}</h3><StatusTag :label="conclusion.label" :type="conclusion.type" /></header>
    <p>责任单位就绪 {{ count(gate.readyUnitCount) }} / {{ count(gate.totalUnitCount) }} · 阻断单位 {{ count(gate.blockedUnitCount) }}</p>
    <ul v-if="gate.blockers?.length"><li v-for="(blocker, index) in gate.blockers" :key="index">{{ blockerMessage(blocker) }}</li></ul>
    <p v-if="gate.required === false" class="gate-note">此项条件不要求当前范围办理。</p>
    <p v-else-if="gate.ready !== true" class="gate-note">统一办理条件尚未通过，请先由相关责任方完成前置事项。</p>
    <p v-else class="gate-note">已满足本次检查条件，正式办理仍须进入原业务工作区核验。</p>
  </article>
</template>

<script>
import { StatusTag } from '@/components/business'
import { academicFlowText, academicFlowCount, academicFlowBlockerMessage } from '../config/academicFlowRegistry.js'
export default {
  name: 'AcademicSchoolGateCard', components: { StatusTag },
  props: { gate: { type: Object, required: true } },
  computed: {
    title() { return academicFlowText(this.gate.label, '学校统一办理条件') },
    conclusion() { return this.gate.required === false ? { label: '本范围不适用', type: 'info' } : this.gate.ready === true ? { label: '条件已满足', type: 'success' } : this.gate.ready === false ? { label: '条件未满足', type: 'warning' } : { label: '条件待核对', type: 'info' } }
  },
  methods: { count: academicFlowCount, blockerMessage: academicFlowBlockerMessage }
}
</script>

<style scoped>
.academic-school-gate { padding:14px 16px; border:1px solid var(--border-base); border-radius:10px; background:var(--bg-card); font-size:12px; line-height:1.7; overflow-wrap:anywhere; }.academic-school-gate header { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }.academic-school-gate h3 { font-size:14px; margin:0; }.academic-school-gate p { margin:10px 0 0; }.academic-school-gate ul { padding-left:18px; margin:10px 0 0; }.gate-note { color:var(--text-secondary); }
</style>
