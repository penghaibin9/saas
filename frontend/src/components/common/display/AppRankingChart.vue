<template>
  <AppChartCard :title="title" :subtitle="subtitle" :loading="loading" :empty="!rows.length" :min-height="minHeight">
    <div class="app-ranking-chart">
      <AppG2Chart class="app-ranking-chart__chart" :spec="chartSpec" :height="height" />
      <div class="app-ranking-chart__list">
        <div
          v-for="row in decoratedRows"
          :key="row.label"
          class="app-ranking-chart__item"
          :class="{ 'is-top': row.rank === 1 }"
        >
          <span class="app-ranking-chart__rank">{{ row.rank }}</span>
          <div class="app-ranking-chart__main">
            <div class="app-ranking-chart__line">
              <span class="app-ranking-chart__label">{{ row.label }}</span>
              <strong>{{ row.value }}{{ unit }}</strong>
            </div>
            <span class="app-ranking-chart__bar"><i :style="{ width: row.percent + '%' }" /></span>
          </div>
        </div>
      </div>
    </div>
    <template v-if="$slots.footer || note" #footer>
      <slot name="footer">
        <span class="app-ranking-chart__note">{{ note }}</span>
      </slot>
    </template>
  </AppChartCard>
</template>

<script>
import AppChartCard from './AppChartCard.vue'
import AppG2Chart from './AppG2Chart.vue'
import { buildBarChartSpec } from './chartPresets'
import { CHART_COLORS } from './chartTheme'

export default {
  name: 'AppRankingChart',
  components: { AppChartCard, AppG2Chart },
  props: {
    title: { type: String, default: '排行分析' },
    subtitle: { type: String, default: '' },
    data: { type: Array, default: () => [] },
    labelField: { type: String, default: 'label' },
    valueField: { type: String, default: 'value' },
    valueLabel: { type: String, default: '数值' },
    unit: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    height: { type: Number, default: 240 },
    minHeight: { type: Number, default: 260 },
    note: { type: String, default: '' },
    listLimit: { type: Number, default: 4 }
  },
  computed: {
    rows() {
      return [...(this.data || [])]
        .filter(Boolean)
        .sort((a, b) => Number(b[this.valueField] || 0) - Number(a[this.valueField] || 0))
    },
    chartSpec() {
      return buildBarChartSpec({
        data: this.rows,
        xField: this.labelField,
        yField: this.valueField,
        horizontal: true,
        valueLabel: this.valueLabel,
        unit: this.unit,
        color: CHART_COLORS.primary
      })
    },
    decoratedRows() {
      const max = Math.max(...this.rows.map((row) => Number(row[this.valueField] || 0)), 1)
      return this.rows.slice(0, this.listLimit).map((row, index) => {
        const value = Number(row[this.valueField] || 0)
        return {
          rank: index + 1,
          label: String(row[this.labelField] ?? ''),
          value,
          percent: Math.max(8, Math.round((value / max) * 100))
        }
      })
    }
  }
}
</script>

<style scoped>
.app-ranking-chart {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px;
  align-items: stretch;
  gap: 16px;
}
.app-ranking-chart__chart {
  min-width: 0;
}
.app-ranking-chart__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 6px 0;
}
.app-ranking-chart__item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.app-ranking-chart__rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: #eef2ff;
  color: #4f46e5;
  font-size: 12px;
  font-weight: 700;
  flex: 0 0 auto;
}
.app-ranking-chart__item.is-top .app-ranking-chart__rank {
  background: linear-gradient(135deg, #2563eb, #06b6d4);
  color: #fff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
}
.app-ranking-chart__main {
  min-width: 0;
  flex: 1;
}
.app-ranking-chart__line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}
.app-ranking-chart__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}
.app-ranking-chart__line strong {
  color: var(--text-primary);
  font-size: var(--font-size-xs);
}
.app-ranking-chart__bar {
  display: block;
  height: 5px;
  border-radius: var(--radius-full);
  background: #edf2f7;
  overflow: hidden;
}
.app-ranking-chart__bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #06b6d4);
}
.app-ranking-chart__note {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
@media (max-width: 780px) {
  .app-ranking-chart {
    grid-template-columns: 1fr;
  }
}
</style>
