<template>
  <AppCard class="wf-overview-card" :hoverable="clickable" @click="onClick">
    <div class="wf-overview-card__label">{{ label }}</div>
    <div class="wf-overview-card__value">
      {{ value }}<span v-if="unit" class="wf-overview-card__unit">{{ unit }}</span>
    </div>
    <div v-if="hint" class="wf-overview-card__hint">{{ hint }}</div>
  </AppCard>
</template>

<script>
/** WorkflowOverviewCard —— 首页概览指标卡（点击可跳转） */
import { AppCard } from '@/components/ui'

export default {
  name: 'WorkflowOverviewCard',
  components: { AppCard },
  props: {
    label: { type: String, required: true },
    value: { type: [Number, String], required: true },
    unit: { type: String, default: '' },
    hint: { type: String, default: '' },
    clickable: { type: Boolean, default: false }
  },
  emits: ['click'],
  methods: {
    onClick() {
      if (this.clickable) this.$emit('click')
    }
  }
}
</script>

<style scoped>
.wf-overview-card {
  padding: var(--card-padding-pc);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.wf-overview-card__label { font-size: var(--font-size-base); color: var(--text-secondary); }
.wf-overview-card__value {
  font-size: var(--font-size-metric);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  font-variant-numeric: var(--font-numeric);
}
.wf-overview-card__unit { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-left: var(--space-1); }
.wf-overview-card__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
