<template>
  <view v-if="trace || content || message" class="adc" :class="toneClass">
    <view class="adc__icon"><text>{{ warnTone ? '!' : 'i' }}</text></view>
    <view class="adc__body">
      <view class="adc__top">
        <text class="adc__eyebrow">规则校验结果</text>
        <text class="adc__state">{{ warnTone ? '需要处理' : '办理说明' }}</text>
      </view>
      <text class="adc__title">{{ displayTitle }}</text>
      <text class="adc__reason">{{ displayReason }}</text>

      <view v-if="resolutionLabels.length" class="adc__next">
        <text class="adc__label">建议下一步</text>
        <view v-for="(label, index) in resolutionLabels" :key="index" class="adc__step">
          <text class="adc__step-no">{{ index + 1 }}</text>
          <text class="adc__next-text">{{ label }}</text>
        </view>
      </view>

      <view class="adc__trust">
        <view class="adc__trust-dot" />
        <text>结果来自学校业务规则实时校验</text>
      </view>

      <view v-if="showAuditMeta" class="adc__meta">
        <text v-if="trace && trace.ruleCode">规则 {{ trace.ruleCode }}</text>
        <text v-if="trace && trace.traceId">Trace {{ trace.traceId }}</text>
        <text v-if="trace && trace.ruleVersion">规则版本 {{ trace.ruleVersion }}</text>
        <text v-if="trace && trace.evaluatedAt">评估时间 {{ trace.evaluatedAt }}</text>
      </view>
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
    warnTone() {
      const decision = String((this.trace && this.trace.decision) || '').toUpperCase()
      return ['DENIED', 'BLOCKED', 'FAILED', 'ABNORMAL'].includes(decision)
    },
    displayTitle() {
      if (this.content && this.content.title) return this.content.title
      const domain = String((this.trace && this.trace.domain) || '').toUpperCase()
      if (domain === 'GRADUATION') return '毕业条件还有待处理事项'
      if (domain === 'SELECTION') return '本次选课暂未通过校验'
      return '当前事项暂未通过校验'
    },
    displayReason() {
      return (this.content && this.content.reason) || this.message || '当前规则暂不允许办理，请按提示核对后再试。'
    },
    resolutionLabels() {
      if (this.content && this.content.nextStep) return [this.content.nextStep]
      const rows = (this.trace && this.trace.availableResolutions) || []
      return rows.map((item) => String((item && item.label) || '').trim()).filter(Boolean).slice(0, 3)
    },
    toneClass() { return this.warnTone ? 'is-warn' : 'is-info' }
  }
}
</script>

<style scoped>
.adc { display: flex; gap: var(--space-3); border: 1px solid rgba(59,130,246,.16); border-radius: 18px; padding: var(--space-4); background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(239,246,255,.9)); box-shadow: var(--shadow-card); }
.adc.is-warn { border-color: rgba(217,119,6,.22); background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,247,237,.94)); }
.adc__icon { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 12px; background: rgba(59,130,246,.10); color: var(--brand-primary); font-size: 17px; font-weight: 800; }
.adc.is-warn .adc__icon { background: rgba(217,119,6,.10); color: #b45309; }
.adc__body { flex: 1; min-width: 0; }
.adc__top { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.adc__eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 1px; color: var(--text-tertiary); }
.adc__state { flex-shrink: 0; font-size: 10px; font-weight: 700; line-height: 20px; padding: 0 8px; border-radius: var(--radius-full); color: var(--brand-primary); background: rgba(59,130,246,.08); }
.adc.is-warn .adc__state { color: #b45309; background: rgba(217,119,6,.10); }
.adc__title { display: block; margin-top: 5px; font-size: var(--font-size-base); font-weight: 700; line-height: 1.45; color: var(--text-primary); }
.adc__reason { display: block; margin-top: 5px; font-size: var(--font-size-sm); line-height: 1.7; color: var(--text-secondary); }
.adc__next { margin-top: var(--space-3); padding: var(--space-3); border-radius: 12px; background: rgba(255,255,255,.72); }
.adc__label { display: block; margin-bottom: 6px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.adc__step { display: flex; align-items: flex-start; gap: var(--space-2); margin-top: 6px; }
.adc__step:first-of-type { margin-top: 0; }
.adc__step-no { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 7px; background: rgba(59,130,246,.09); color: var(--brand-primary); font-size: 10px; font-weight: 700; }
.adc.is-warn .adc__step-no { background: rgba(217,119,6,.10); color: #b45309; }
.adc__next-text { flex: 1; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); line-height: 1.55; }
.adc__trust { display: flex; align-items: center; gap: 6px; margin-top: var(--space-3); }
.adc__trust-dot { width: 6px; height: 6px; border-radius: var(--radius-full); background: #16a34a; }
.adc__trust text { font-size: 10px; color: var(--text-tertiary); }
.adc__meta { display: flex; flex-direction: column; gap: 3px; margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); font-size: 10px; color: var(--text-tertiary); word-break: break-all; }
</style>
