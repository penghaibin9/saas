<template>
  <AppChartCard :title="title" :subtitle="subtitle" :loading="loading" :empty="!data.length" :min-height="minHeight">
    <div class="app-funnel-chart__stages">
      <div v-for="item in stageRows" :key="item.label" class="app-funnel-chart__stage">
        <span class="app-funnel-chart__stage-name">{{ item.label }}</span>
        <strong>{{ item.value }}{{ unit }}</strong>
        <em>{{ item.rate }}%</em>
      </div>
    </div>

    <AppG2Chart :spec="chartSpec" :height="height" />

    <template v-if="showSummary" #footer>
      <div class="app-funnel-chart__summary">
        <span>{{ summary }}</span>
        <b v-if="dropOffText">{{ dropOffText }}</b>
      </div>
    </template>
  </AppChartCard>
</template>

<script>
import AppChartCard from './AppChartCard.vue'
import AppG2Chart from './AppG2Chart.vue'
import { buildFunnelChartSpec } from './chartPresets'

export default {
  name: 'AppFunnelChart',
  components: { AppChartCard, AppG2Chart },
  props: {
    title: { type: String, default: '流程漏斗' },
    subtitle: { type: String, default: '' },
    data: { type: Array, default: () => [] },
    stageField: { type: String, default: 'label' },
    valueField: { type: String, default: 'value' },
    valueLabel: { type: String, default: '人数' },
    unit: { type: String, default: '人' },
    loading: { type: Boolean, default: false },
    height: { type: Number, default: 220 },
    minHeight: { type: Number, default: 320 },
    showSummary: { type: Boolean, default: true }
  },
  computed: {
    chartSpec() {
      return buildFunnelChartSpec({
        data: this.data,
        stageField: this.stageField,
        valueField: this.valueField,
        valueLabel: this.valueLabel,
        unit: this.unit
      })
    },
    stageRows() {
      const first = Number(this.data?.[0]?.[this.valueField] || 0) || 1
      return (this.data || []).map((row) => {
        const value = Number(row?.[this.valueField] || 0)
        return {
          label: String(row?.[this.stageField] ?? ''),
          value,
          rate: Math.round((value / first) * 100)
        }
      })
    },
    summary() {
      const first = Number(this.data?.[0]?.[this.valueField] || 0)
      const last = Number(this.data?.[this.data.length - 1]?.[this.valueField] || 0)
      if (!first) return '暂无可计算的转化率'
      return `整体转化率 ${Math.round((last / first) * 100)}%`
    },
    dropOffText() {
      if (!this.data?.length) return ''
      const first = Number(this.data?.[0]?.[this.valueField] || 0)
      const last = Number(this.data?.[this.data.length - 1]?.[this.valueField] || 0)
      if (!first || first <= last) return ''
      return `流失 ${first - last}${this.unit}`
    }
  }
}
</script>

<style scoped>
.app-funnel-chart__stages {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.app-funnel-chart__stage {
  position: relative;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: var(--radius-base);
  background: #f8fafc;
  overflow: hidden;
}
.app-funnel-chart__stage::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, #2563eb, #06b6d4);
}
.app-funnel-chart__stage-name {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-funnel-chart__stage strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.2;
  font-family: var(--font-numeric);
}
.app-funnel-chart__stage em {
  position: absolute;
  right: 10px;
  bottom: 9px;
  color: #2563eb;
  font-style: normal;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}
.app-funnel-chart__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.app-funnel-chart__summary b {
  color: var(--warning-600);
  font-weight: var(--font-weight-semibold);
}
</style>
