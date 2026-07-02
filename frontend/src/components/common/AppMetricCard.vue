<template>
  <div
    class="app-metric-card"
    :class="[`is-accent-${accentTone}`, { 'is-drillable': drillable }]"
    @click="onClick"
  >
    <div class="app-metric-card__title">
      {{ title }}
      <span v-if="description" class="app-metric-card__desc" :title="description">?</span>
    </div>
    <div class="app-metric-card__value-row">
      <span class="app-metric-card__value">{{ value }}</span>
      <span v-if="unit" class="app-metric-card__unit">{{ unit }}</span>
    </div>
    <div class="app-metric-card__footer">
      <span v-if="updatedAt" class="app-metric-card__time">更新于 {{ updatedAt }}</span>
      <span v-if="trendLabel" class="app-metric-card__trend" :class="`is-${quality}`">
        <span class="app-metric-card__arrow">{{ arrow }}</span>
        {{ trendLabel }}
      </span>
    </div>
  </div>
</template>

<script>
/**
 * AppMetricCard 指标卡
 * 数据契约见 V2.1 §3.3.1 MetricCardData。
 * accent: 顶部状态色条语义（primary|risk|warning|success），默认由 trendQuality 推断
 */
export default {
  name: 'AppMetricCard',
  props: {
    title: { type: String, required: true },
    value: { type: [Number, String], required: true },
    unit: { type: String, default: '' },
    description: { type: String, default: '' },
    trendType: {
      type: String,
      default: 'flat',
      validator: (v) => ['up', 'down', 'flat'].includes(v)
    },
    trendQuality: {
      type: String,
      default: 'neutral',
      validator: (v) => ['good', 'bad', 'neutral'].includes(v)
    },
    trendLabel: { type: String, default: '' },
    accent: {
      type: String,
      default: '',
      validator: (v) => !v || ['primary', 'risk', 'warning', 'success'].includes(v)
    },
    drillable: { type: Boolean, default: false },
    drillTarget: { type: String, default: '' },
    updatedAt: { type: String, default: '' }
  },
  emits: ['drill'],
  computed: {
    quality() {
      return this.trendQuality || 'neutral'
    },
    accentTone() {
      if (this.accent) return this.accent
      if (this.quality === 'bad') return 'risk'
      if (this.quality === 'good') return 'success'
      return 'primary'
    },
    arrow() {
      if (this.trendType === 'up') return '↑'
      if (this.trendType === 'down') return '↓'
      return '—'
    }
  },
  methods: {
    onClick() {
      if (this.drillable) this.$emit('drill', this.drillTarget)
    }
  }
}
</script>

<style scoped>
.app-metric-card {
  position: relative;
  overflow: hidden;
  background: var(--bg-card);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card-sm);
  padding: var(--space-4) var(--space-5);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  min-height: 132px;
  max-height: 140px;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}
.app-metric-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--primary-600);
}
.app-metric-card.is-accent-primary::before {
  background: var(--primary-600);
}
.app-metric-card.is-accent-risk::before {
  background: var(--danger-500);
}
.app-metric-card.is-accent-warning::before {
  background: var(--warning-500);
}
.app-metric-card.is-accent-success::before {
  background: var(--success-500);
}
.is-drillable {
  cursor: pointer;
}
.is-drillable:hover {
  border-color: var(--primary-100);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.app-metric-card__title {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-1);
  line-height: 1.4;
}
.app-metric-card__desc {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 14px;
  text-align: center;
  cursor: help;
}
.app-metric-card__value-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
  flex: 1;
}
.app-metric-card__value {
  font-size: 38px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-variant-numeric: var(--font-numeric);
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.app-metric-card__unit {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
}
.app-metric-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 18px;
  margin-top: auto;
}
.app-metric-card__trend {
  font-size: var(--font-size-xs);
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-weight: var(--font-weight-medium);
  margin-left: auto;
}
.app-metric-card__trend.is-good {
  color: var(--success-600);
}
.app-metric-card__trend.is-bad {
  color: var(--danger-500);
}
.app-metric-card__trend.is-neutral {
  color: var(--text-tertiary);
}
.app-metric-card__time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}
</style>
