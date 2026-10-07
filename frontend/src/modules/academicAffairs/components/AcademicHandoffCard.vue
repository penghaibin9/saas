<template>
  <aside class="academic-handoff" aria-label="下一责任">
    <div><small>完成后交给下一责任方</small><strong>{{ text(nextStep?.label, '下一步尚未明确，请先完成当前责任事项') }}</strong></div>
    <template v-if="nextStep?.responsibility"><p>{{ responsibility.orgName }} · {{ responsibility.positionLabel }} · {{ responsibility.assigneeLabel }}</p><p v-if="!responsibility.resolved" role="status">{{ responsibility.reason }}</p></template>
    <AppButton v-if="nextStep?.route && canOpen(nextStep.route)" variant="ghost" @click="$emit('navigate', nextStep.route)">查看下一责任事项</AppButton>
    <p v-else-if="nextStep?.route" class="handoff-note">由下一责任方按其授权范围继续办理。</p>
  </aside>
</template>

<script>
import { AppButton } from '@/components/ui'
import { academicFlowText, academicFlowResponsibility } from '../config/academicFlowRegistry.js'
export default {
  name: 'AcademicHandoffCard', components: { AppButton }, emits: ['navigate'],
  props: { nextStep: { type: Object, default: null }, canOpen: { type: Function, default: () => false } },
  computed: { responsibility() { return academicFlowResponsibility(this.nextStep?.responsibility) } },
  methods: { text: academicFlowText }
}
</script>

<style scoped>
.academic-handoff { padding:12px 14px; border-radius:8px; background:var(--pri-bg,var(--bg-card)); font-size:12px; line-height:1.7; overflow-wrap:anywhere; }.academic-handoff div { display:grid; gap:4px; }.academic-handoff small,.handoff-note { color:var(--text-secondary); }.academic-handoff strong { font-size:13px; }.academic-handoff p { margin:7px 0; }
</style>
