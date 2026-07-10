<template>
  <div class="app-g2-chart" :class="{ 'is-error': errorMessage, 'is-loading': loading }" :style="{ height: resolvedHeight }">
    <div v-if="loading && !errorMessage" class="app-g2-chart__loading">图表加载中…</div>
    <div v-if="errorMessage" class="app-g2-chart__error">
      <strong>图表渲染失败</strong>
      <span>{{ errorMessage }}</span>
    </div>
    <div ref="container" class="app-g2-chart__canvas" />
  </div>
</template>

<script>
/**
 * AppG2Chart — AntV G2 统一渲染底座。
 * G2 库按需动态加载，避免非图表页首屏下载 1.3MB 图表包。
 */
import { baseChartSpec } from './chartTheme'

let g2ModulePromise = null
function loadG2() {
  if (!g2ModulePromise) g2ModulePromise = import('@antv/g2')
  return g2ModulePromise
}

function cleanSpec(value) {
  if (Array.isArray(value)) {
    return value.map(cleanSpec).filter((item) => item !== undefined)
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).reduce((acc, [key, item]) => {
      if (item !== undefined) acc[key] = cleanSpec(item)
      return acc
    }, {})
  }
  return value
}

export default {
  name: 'AppG2Chart',
  props: {
    spec: { type: Object, required: true },
    height: { type: [Number, String], default: 240 }
  },
  emits: ['rendered', 'error'],
  data() {
    return {
      chart: null,
      renderSeq: 0,
      renderTimer: null,
      errorMessage: '',
      loading: false
    }
  },
  computed: {
    resolvedHeight() {
      return typeof this.height === 'number' ? `${this.height}px` : this.height
    }
  },
  watch: {
    spec: {
      deep: true,
      handler() {
        this.scheduleRender()
      }
    },
    height() {
      this.scheduleRender()
    }
  },
  mounted() {
    this.scheduleRender()
  },
  beforeUnmount() {
    if (this.renderTimer) clearTimeout(this.renderTimer)
    this.destroyChart()
  },
  methods: {
    scheduleRender() {
      if (this.renderTimer) clearTimeout(this.renderTimer)
      this.renderTimer = setTimeout(() => this.renderChart(), 32)
    },
    destroyChart() {
      if (this.chart) {
        this.chart.destroy()
        this.chart = null
      }
    },
    async renderChart() {
      if (!this.$refs.container || !this.spec) return
      const seq = ++this.renderSeq
      this.destroyChart()
      this.errorMessage = ''
      this.loading = true
      try {
        const { Chart } = await loadG2()
        if (seq !== this.renderSeq) return
        this.chart = new Chart({
          container: this.$refs.container,
          autoFit: true,
          height: Number.parseInt(this.resolvedHeight, 10) || 240
        })
        this.chart.options(cleanSpec(baseChartSpec(this.spec)))
        await this.chart.render()
        if (seq === this.renderSeq) {
          this.loading = false
          this.$emit('rendered', this.chart)
        }
      } catch (e) {
        if (seq !== this.renderSeq) return
        this.loading = false
        this.destroyChart()
        this.errorMessage = e?.message || 'render error'
        this.$emit('error', e)
      }
    }
  }
}
</script>

<style scoped>
.app-g2-chart {
  width: 100%;
  min-width: 0;
  position: relative;
}
.app-g2-chart__canvas {
  width: 100%;
  height: 100%;
}
.app-g2-chart.is-loading .app-g2-chart__canvas {
  visibility: hidden;
}
.app-g2-chart.is-error .app-g2-chart__canvas {
  display: none;
}
.app-g2-chart__loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.app-g2-chart__error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 100%;
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-base);
  color: var(--danger-600, #dc2626);
  background: var(--danger-50, #fef2f2);
  font-size: var(--font-size-sm);
  text-align: center;
  padding: var(--space-3);
}
.app-g2-chart__error span {
  max-width: 100%;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  word-break: break-word;
}
</style>
