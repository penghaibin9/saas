<template>
  <AppChartCard :title="title" :subtitle="subtitle" :loading="loading" :empty="!data.length" :min-height="minHeight">
    <template #toolbar>
      <div class="app-drill-chart__crumbs">
        <button
          v-for="(item, index) in breadcrumbs"
          :key="item.key || item.label"
          type="button"
          class="app-drill-chart__crumb"
          :class="{ 'is-current': index === breadcrumbs.length - 1 }"
          @click="$emit('breadcrumb-click', item, index)"
        >
          {{ item.label }}
        </button>
      </div>
    </template>

    <div class="app-drill-chart__summary">
      <span>维度数 <b>{{ data.length }}</b></span>
      <span>最高值 <b>{{ maxValue }}{{ unit }}</b></span>
      <span>平均值 <b>{{ avgValue }}{{ unit }}</b></span>
    </div>

    <AppG2Chart :spec="chartSpec" :height="height" />

    <div v-if="data.length" class="app-drill-chart__list">
      <button
        v-for="row in decoratedRows"
        :key="row.label"
        type="button"
        class="app-drill-chart__row"
        @click="$emit('drill', row.raw)"
      >
        <span class="app-drill-chart__name">{{ row.label }}</span>
        <span class="app-drill-chart__meter"><i :style="{ width: row.percent + '%' }" /></span>
        <b>{{ row.value }}{{ unit }}</b>
      </button>
    </div>
  </AppChartCard>
</template>

<script>
import AppChartCard from './AppChartCard.vue'
import AppG2Chart from './AppG2Chart.vue'
import { buildBarChartSpec } from './chartPresets'
import { CHART_COLORS } from './chartTheme'

export default {
  name: 'AppDrilldownChartCard',
  components: { AppChartCard, AppG2Chart },
  props: {
    title: { type: String, default: '下钻分析' },
    subtitle: { type: String, default: '' },
    data: { type: Array, default: () => [] },
    breadcrumbs: { type: Array, default: () => [{ label: '全部', key: 'all' }] },
    labelField: { type: String, default: 'label' },
    valueField: { type: String, default: 'value' },
    valueLabel: { type: String, default: '数量' },
    unit: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    height: { type: Number, default: 210 },
    minHeight: { type: Number, default: 360 }
  },
  emits: ['drill', 'breadcrumb-click'],
  computed: {
    chartSpec() {
      return buildBarChartSpec({
        data: this.data,
        xField: this.labelField,
        yField: this.valueField,
        horizontal: true,
        valueLabel: this.valueLabel,
        unit: this.unit,
        color: CHART_COLORS.success
      })
    },
    maxValue() {
      return Math.max(...(this.data || []).map((row) => Number(row?.[this.valueField] || 0)), 0)
    },
    avgValue() {
      if (!this.data?.length) return 0
      const total = this.data.reduce((sum, row) => sum + Number(row?.[this.valueField] || 0), 0)
      return Math.round(total / this.data.length)
    },
    decoratedRows() {
      const max = this.maxValue || 1
      return (this.data || []).map((row) => {
        const value = Number(row?.[this.valueField] || 0)
        return {
          raw: row,
          label: String(row?.[this.labelField] ?? ''),
          value,
          percent: Math.max(6, Math.round((value / max) * 100))
        }
      })
    }
  }
}
</script>

<style scoped>
.app-drill-chart__crumbs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.app-drill-chart__crumb {
  height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: var(--radius-full);
  background: #fff;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all 0.15s ease;
}
.app-drill-chart__crumb:hover {
  border-color: rgba(37, 99, 235, 0.35);
  color: var(--primary-700);
}
.app-drill-chart__crumb.is-current {
  border-color: rgba(37, 99, 235, 0.28);
  color: var(--primary-700);
  background: var(--primary-50);
  font-weight: var(--font-weight-semibold);
}
.app-drill-chart__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.app-drill-chart__summary span {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  height: 34px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: var(--radius-base);
  background: #f8fafc;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.app-drill-chart__summary b {
  color: var(--text-primary);
  font-family: var(--font-numeric);
}
.app-drill-chart__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
  margin-top: 12px;
}
.app-drill-chart__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 64px auto;
  align-items: center;
  gap: 10px;
  height: 38px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: var(--radius-base);
  background: #fff;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.app-drill-chart__row:hover {
  border-color: rgba(37, 99, 235, 0.35);
  background: #f8fbff;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}
.app-drill-chart__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-drill-chart__meter {
  display: block;
  height: 5px;
  border-radius: var(--radius-full);
  background: #edf2f7;
  overflow: hidden;
}
.app-drill-chart__meter i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #10b981, #06b6d4);
}
.app-drill-chart__row b {
  color: var(--text-primary);
  font-family: var(--font-numeric);
}
@media (max-width: 640px) {
  .app-drill-chart__summary {
    grid-template-columns: 1fr;
  }
}
</style>
