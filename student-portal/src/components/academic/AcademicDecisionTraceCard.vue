<template>
  <section v-if="trace || content || message" class="decision-card" :class="toneClass" role="status">
    <div class="decision-card__head">
      <strong>{{ displayTitle }}</strong>
      <span v-if="trace?.ruleCode" class="decision-card__code">{{ trace.ruleCode }}</span>
    </div>
    <p class="decision-card__reason">{{ displayReason }}</p>
    <div v-if="displayNextStep" class="decision-card__next">
      <span>下一步</span>
      <strong>{{ displayNextStep }}</strong>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  trace: { type: Object, default: null },
  content: { type: Object, default: null },
  message: { type: String, default: '' }
})

const displayTitle = computed(() => {
  if (props.content?.title) return props.content.title
  const domain = String(props.trace?.domain || '').toUpperCase()
  if (domain === 'GRADUATION') return '毕业资格存在待处理项'
  if (domain === 'SELECTION') return '暂时无法选课'
  return '暂时无法办理'
})

const displayReason = computed(() =>
  props.content?.reason || props.message || '当前规则暂不允许办理。')

const displayNextStep = computed(() => {
  if (props.content?.nextStep) return props.content.nextStep
  const rows = Array.isArray(props.trace?.availableResolutions) ? props.trace.availableResolutions : []
  return rows[0]?.label || ''
})

const toneClass = computed(() => {
  const decision = String(props.trace?.decision || '').toUpperCase()
  return ['DENIED', 'BLOCKED', 'FAILED', 'ABNORMAL'].includes(decision) ? 'is-warn' : 'is-info'
})
</script>

<style scoped>
.decision-card {
  padding: 16px 18px;
  border: 1px solid var(--pri-100);
  border-radius: 13px;
  background: var(--pri-50);
}
.decision-card.is-warn {
  border-color: #fed7aa;
  background: #fff7ed;
}
.decision-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  color: var(--t1);
}
.decision-card__code {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, .06);
  color: var(--t3);
  font-size: 11px;
}
.decision-card__reason {
  margin: 8px 0 0;
  color: var(--t2);
  font-size: 13px;
  line-height: 1.65;
}
.decision-card__next {
  display: grid;
  gap: 4px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}
.decision-card__next span {
  color: var(--t4);
  font-size: 11px;
}
.decision-card__next strong {
  color: var(--t1);
  font-size: 13px;
  line-height: 1.55;
}
</style>
