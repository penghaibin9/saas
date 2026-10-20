<template>
  <AppChartCard :title="title" :subtitle="subtitle" :loading="loading" :empty="!data.length" :min-height="minHeight">
    <div class="app-stacked-chart__legend">
      <span v-for="item in legendItems" :key="item.label" class="app-stacked-chart__chip">
        <i :style="{ background: item.color }" />
        <span>{{ item.label }}</span>
        <b>{{ item.value }}{{ unit }}</b>
      </span>
    </div>
    <AppG2Chart :spec="chartSpec" :height="height" />
  </AppChartCard>
</template>

<script>
import AppChartCard from './AppChartCard.vue'
import AppG2Chart from './AppG2Chart.vue'
import { buildStackedBarChartSpec } from './chartPresets'
import { CHART_PALETTE } from './chartTheme'

export default {
  name: 'AppStackedBarChart',
  components: { AppChartCard, AppG2Chart },
  props: {
    title: { type: String, default: '堆叠分析' },
    subtitle: { type: String, default: '' },
    data: { type: Array, default: () => [] },
    xField: { type: String, default: 'label' },
    yField: { type: String, default: 'value' },
    seriesField: { type: String, default: 'type' },
    valueLabel: { type: String, default: '数量' },
    unit: { type: String, default: '' },
    horizontal: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    height: { type: Number, default: 240 },
    minHeight: { type: Number, default: 260 }
  },
  computed: {
    chartSpec() {
      return buildStackedBarChartSpec({
        data: this.data,
        xField: this.xField,
        yField: this.yField,
        seriesField: this.seriesField,
        valueLabel: this.valueLabel,
        unit: this.unit,
        horizontal: this.horizontal
      })
    },
    legendItems() {
      const totals = new Map()
      ;(this.data || []).forEach((row) => {
        const label = String(row?.[this.seriesField] ?? '')
        totals.set(label, (totals.get(label) || 0) + Number(row?.[this.yField] || 0))
      })
      return Array.from(totals.entries()).map(([label, value], index) => ({
        label,
        value,
        color: CHART_PALETTE[index % CHART_PALETTE.length]
      }))
    }
  }
}
</script>

<style scoped>
.app-stacked-chart__legend {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.app-stacked-chart__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: var(--radius-full);
  background: #f8fafc;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.app-stacked-chart__chip i {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}
.app-stacked-chart__chip b {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}
</style>
