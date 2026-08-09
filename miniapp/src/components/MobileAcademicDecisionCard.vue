<template>
  <view v-if="trace || content || message" class="adc" :class="toneClass">
    <view class="adc__head">
      <text class="adc__title">{{ displayTitle }}</text>
      <text v-if="trace && trace.ruleCode" class="adc__code">{{ trace.ruleCode }}</text>
    </view>
    <text class="adc__reason">{{ displayReason }}</text>
    <view v-if="displayNextStep" class="adc__next">
      <text class="adc__label">下一步</text>
      <text class="adc__next-text">{{ displayNextStep }}</text>
    </view>
    <view v-if="showAuditMeta" class="adc__meta">
      <text v-if="trace.traceId">Trace {{ trace.traceId }}</text>
      <text v-if="trace.ruleVersion">规则版本 {{ trace.ruleVersion }}</text>
      <text v-if="trace.evaluatedAt">评估时间 {{ trace.evaluatedAt }}</text>
    </view>
  </view>
</template>

<script>
export default {
  name: 'MobileAcademicDecisionCard',
  props: {
    trace: { type: Object, default: null },
    content: { type: Object, default: null },
    message: { type: String, default: '' },
    audience: { type: String, default: 'student' }
  },
  computed: {
    showAuditMeta() { return this.audience === 'teacher' || this.audience === 'admin' },
    displayTitle() {
      if (this.content && this.content.title) return this.content.title
      const domain = String((this.trace && this.trace.domain) || '').toUpperCase()
      if (domain === 'GRADUATION') return '毕业资格存在待处理项'
      if (domain === 'SELECTION') return '暂时无法选课'
      return '暂时无法办理'
    },
    displayReason() {
      return (this.content && this.content.reason) || this.message || '当前规则暂不允许办理。'
    },
    displayNextStep() {
      if (this.content && this.content.nextStep) return this.content.nextStep
      const rows = (this.trace && this.trace.availableResolutions) || []
      return rows.length && rows[0] && rows[0].label ? rows[0].label : ''
    },
    toneClass() {
      const decision = String((this.trace && this.trace.decision) || '').toUpperCase()
      return ['DENIED', 'BLOCKED', 'FAILED', 'ABNORMAL'].includes(decision) ? 'is-warn' : 'is-info'
    }
  }
}
</script>

<style scoped>
.adc { border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: var(--space-4); background: var(--bg-card); box-shadow: var(--shadow-card); }
.adc.is-warn { border-color: rgba(217,119,6,.28); background: rgba(255,247,237,.92); }
.adc__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-2); }
.adc__title { font-size: var(--font-size-base); font-weight: 700; color: var(--text-primary); }
.adc__code { flex-shrink: 0; font-size: 10px; line-height: 18px; padding: 0 7px; border-radius: var(--radius-full); color: var(--text-tertiary); background: rgba(15,23,42,.06); }
.adc__reason { display: block; margin-top: var(--space-2); font-size: var(--font-size-sm); line-height: 1.65; color: var(--text-secondary); }
.adc__next { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.adc__label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.adc__next-text { display: block; margin-top: 3px; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); line-height: 1.55; }
.adc__meta { display: flex; flex-direction: column; gap: 3px; margin-top: var(--space-3); font-size: 10px; color: var(--text-tertiary); word-break: break-all; }
</style>
