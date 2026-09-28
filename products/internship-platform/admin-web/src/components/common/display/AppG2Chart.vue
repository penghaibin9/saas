<template>
  <div ref="root" class="app-g2-chart" :class="{ 'is-error': errorMessage }" :style="{ height: resolvedHeight + 'px' }">
    <div v-if="errorMessage" class="app-g2-chart__error">
      <strong>图表渲染失败</strong>
      <span>{{ errorMessage }}</span>
    </div>
    <template v-else-if="!rows.length">
      <div class="app-g2-chart__empty">暂无数据</div>
    </template>
    <template v-else>
      <div v-if="legendItems.length && legendPosition === 'top'" class="app-g2-chart__legend">
        <span v-for="item in legendItems" :key="'lt-' + item.label" class="app-g2-chart__legend-item">
          <i :style="{ background: item.color }" />{{ item.label }}
        </span>
      </div>
      <svg
        :width="layout.width"
        :height="layout.plotHeight"
        class="app-g2-chart__svg"
        @mousemove="onMouseMove"
        @mouseleave="hoverCategory = ''"
      >
        <line
          v-for="g in gridLines"
          :key="g.key"
          :x1="g.x1" :y1="g.y1" :x2="g.x2" :y2="g.y2"
          class="app-g2-chart__grid"
        />
        <text
          v-for="t in valueTicks"
          :key="t.key"
          :x="t.x" :y="t.y" :text-anchor="t.anchor" dominant-baseline="middle"
          class="app-g2-chart__tick"
        >{{ t.label }}</text>
        <text
          v-for="t in categoryTicks"
          :key="t.key"
          :x="t.x" :y="t.y" :text-anchor="t.anchor" :dominant-baseline="t.baseline"
          class="app-g2-chart__tick app-g2-chart__tick--category"
        >{{ t.label }}</text>

        <template v-if="!isLine">
          <path v-for="bar in bars" :key="bar.key" :d="bar.path" :fill="bar.color" :fill-opacity="barOpacity" />
        </template>

        <g v-for="s in lineSeries" :key="s.key">
          <path :d="s.path" fill="none" :stroke="s.color" :stroke-width="lineWidth" stroke-linejoin="round" stroke-linecap="round" />
          <circle v-for="p in s.points" :key="p.key" :cx="p.x" :cy="p.y" r="3" :fill="s.color" />
        </g>

        <rect
          v-for="h in hitAreas"
          :key="h.key"
          :x="h.x" :y="h.y" :width="h.width" :height="h.height"
          fill="transparent"
          @mouseenter="hoverCategory = h.category"
        />
      </svg>
      <div v-if="legendItems.length && legendPosition === 'bottom'" class="app-g2-chart__legend">
        <span v-for="item in legendItems" :key="'lb-' + item.label" class="app-g2-chart__legend-item">
          <i :style="{ background: item.color }" />{{ item.label }}
        </span>
      </div>
      <div v-if="tooltip" class="app-g2-chart__tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
        <div class="app-g2-chart__tooltip-title">{{ tooltip.title }}</div>
        <div v-for="row in tooltip.rows" :key="row.label" class="app-g2-chart__tooltip-row">
          <i :style="{ background: row.color }" /><span>{{ row.label }}</span><b>{{ row.value }}</b>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
/**
 * AppG2Chart — 轻量图表渲染底座（纯 SVG，无第三方图表库）。
 *
 * 2026-07-18 替换：原实现基于 @antv/g2（动态加载约 1.3MB），实测在浏览器自动化环境下
 * Chart.render() 的 Promise 会挂起不 resolve、画布全程空白（见施工记录 CC-真实交互业务巡检），
 * 用户反馈同一问题在真实浏览器中同样"又大又卡"。改为零依赖手写 SVG 渲染，同步出图，不存在
 * 渲染管线挂起的可能；同时把 vendor 体积从 1.3MB 降到 0。
 *
 * 对外 API 完全不变：仍接收一个「G2 风格」的 spec 对象（type/data/encode/coordinate/transform/
 * style/axis/legend/tooltip/scale），仍复用 chartTheme.js 的 baseChartSpec() 补主题默认值——
 * 全仓所有调用方（chartPresets.js 的 4 个 builder + 6 个页面手写 spec）零改动即可直接工作。
 * 只解析仓库内真实用到的子集：
 *  - type: 'interval'（柱状，含 coordinate.transform=[transpose] 横向、transform=[stackY] 堆叠）
 *  - type: 'line'（多系列折线，shape:'smooth' 走三次贝塞尔平滑）
 *  - encode.x/y/color、scale.color.range、style.fill/fillOpacity/radius(Top|Bottom)(Left|Right)/lineWidth、
 *    axis.y.labelFormatter（横向柱状类目轴截断）、legend.color.position、
 *    tooltip.title(row)/items[0].valueFormatter(value)
 * 不支持饼图/漏斗/复合 view 等 spec 形态——全仓搜索确认目前没有任何页面真实使用这些形态
 * （AppFunnelChart/AppDrilldownChartCard/buildDonutChartSpec/buildTrendChartSpec 均无调用点）。
 */
import { CHART_PALETTE, baseChartSpec, compactNumber } from './chartTheme'

let measureCtx = null
function measureTextWidth(text, font) {
  if (!measureCtx) measureCtx = document.createElement('canvas').getContext('2d')
  measureCtx.font = font
  return measureCtx.measureText(text || '').width
}

function niceTicks(maxValue, targetCount = 4) {
  if (!(maxValue > 0)) return [0, 1]
  const rawStep = maxValue / targetCount
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const residual = rawStep / magnitude
  const niceResidual = residual > 5 ? 10 : residual > 2 ? 5 : residual > 1 ? 2 : 1
  const step = niceResidual * magnitude
  const niceMax = Math.ceil(maxValue / step) * step
  const ticks = []
  for (let v = 0; v <= niceMax + step * 0.5; v += step) ticks.push(Math.round(v * 1e6) / 1e6)
  return ticks
}

function roundedRectPath(x, y, w, h, tl, tr, br, bl) {
  if (w <= 0 || h <= 0) return ''
  const rTl = Math.max(0, Math.min(tl, w / 2, h / 2))
  const rTr = Math.max(0, Math.min(tr, w / 2, h / 2))
  const rBr = Math.max(0, Math.min(br, w / 2, h / 2))
  const rBl = Math.max(0, Math.min(bl, w / 2, h / 2))
  return `M${x + rTl},${y} H${x + w - rTr} A${rTr},${rTr} 0 0 1 ${x + w},${y + rTr} ` +
    `V${y + h - rBr} A${rBr},${rBr} 0 0 1 ${x + w - rBr},${y + h} H${x + rBl} ` +
    `A${rBl},${rBl} 0 0 1 ${x},${y + h - rBl} V${y + rTl} A${rTl},${rTl} 0 0 1 ${x + rTl},${y} Z`
}

function smoothPath(points) {
  if (points.length === 0) return ''
  if (points.length === 1) return `M${points[0].x},${points[0].y}`
  let d = `M${points[0].x},${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2] || p2
    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6
    d += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`
  }
  return d
}

function straightPath(points) {
  if (!points.length) return ''
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
}

export default {
  name: 'AppG2Chart',
  props: {
    spec: { type: Object, required: true },
    height: { type: [Number, String], default: 240 }
  },
  emits: ['rendered', 'error'],
  data() {
    return { width: 320, errorMessage: '', hoverCategory: '', resizeObserver: null }
  },
  computed: {
    resolvedHeight() {
      return typeof this.height === 'number' ? this.height : Number.parseInt(this.height, 10) || 240
    },
    mergedSpec() {
      try {
        return baseChartSpec(this.spec || {})
      } catch {
        return { data: [] }
      }
    },
    isLine() { return this.mergedSpec.type === 'line' },
    isHorizontal() { return (this.mergedSpec.coordinate?.transform || []).some((t) => t.type === 'transpose') },
    isStacked() { return (this.mergedSpec.transform || []).some((t) => t.type === 'stackY') },
    xField() { return this.mergedSpec.encode?.x },
    yField() { return this.mergedSpec.encode?.y },
    colorField() { return this.mergedSpec.encode?.color },
    rows() { return Array.isArray(this.mergedSpec.data) ? this.mergedSpec.data : [] },
    palette() { return this.mergedSpec.scale?.color?.range?.length ? this.mergedSpec.scale.color.range : CHART_PALETTE },
    styleConfig() { return this.mergedSpec.style || {} },
    barOpacity() { return this.styleConfig.fillOpacity != null ? this.styleConfig.fillOpacity : 1 },
    lineWidth() { return this.styleConfig.lineWidth || 2 },
    legendConfig() { return this.mergedSpec.legend },
    legendPosition() { return this.legendConfig?.color?.position === 'bottom' ? 'bottom' : 'top' },
    tooltipConfig() { return this.mergedSpec.tooltip },
    yLabelFormatter() {
      const fn = this.mergedSpec.axis?.y?.labelFormatter
      return typeof fn === 'function' ? fn : (v) => v
    },
    categories() {
      const seen = new Set()
      const list = []
      this.rows.forEach((r) => {
        const v = String(r?.[this.xField] ?? '')
        if (!seen.has(v)) { seen.add(v); list.push(v) }
      })
      return list
    },
    seriesKeys() {
      if (!this.colorField) return [null]
      const seen = new Set()
      const list = []
      this.rows.forEach((r) => {
        const v = String(r?.[this.colorField] ?? '')
        if (!seen.has(v)) { seen.add(v); list.push(v) }
      })
      return list.length ? list : [null]
    },
    rowLookup() {
      const map = new Map()
      this.rows.forEach((r) => {
        const cat = String(r?.[this.xField] ?? '')
        const ser = this.colorField ? String(r?.[this.colorField] ?? '') : '__single__'
        map.set(cat + '::' + ser, r)
      })
      return map
    },
    categoryLabels() {
      return this.categories.map((c) => (this.isHorizontal ? String(this.yLabelFormatter(c)) : c))
    },
    maxValue() {
      if (this.isStacked) {
        let max = 0
        this.categories.forEach((cat) => {
          let sum = 0
          this.seriesKeys.forEach((ser) => { sum += this.valueFor(cat, ser) })
          if (sum > max) max = sum
        })
        return max
      }
      let max = 0
      this.rows.forEach((r) => { const v = Number(r?.[this.yField] || 0); if (v > max) max = v })
      return max
    },
    ticks() { return niceTicks(this.maxValue) },
    niceMax() { return this.ticks[this.ticks.length - 1] || 1 },
    leftMargin() {
      if (this.isHorizontal) {
        const widths = this.categoryLabels.map((l) => measureTextWidth(l, '11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'))
        return Math.min(140, Math.max(36, Math.ceil(Math.max(0, ...widths, 0)) + 14))
      }
      const widths = this.ticks.map((t) => measureTextWidth(compactNumber(t), '11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'))
      return Math.max(28, Math.ceil(Math.max(0, ...widths, 0)) + 12)
    },
    layout() {
      const legendH = this.legendItems.length ? 30 : 0
      const padTop = 12
      const padRight = 14
      const padBottom = this.isHorizontal ? 26 : 30
      const plotHeight = this.resolvedHeight - legendH
      const plotX0 = this.leftMargin
      const plotX1 = Math.max(plotX0 + 10, this.width - padRight)
      const plotY0 = padTop
      const plotY1 = Math.max(plotY0 + 10, plotHeight - padBottom)
      return { width: this.width, plotHeight, plotX0, plotX1, plotY0, plotY1 }
    },
    valueScaleFn() {
      const { plotX0, plotX1, plotY0, plotY1 } = this.layout
      if (this.isHorizontal) return (v) => plotX0 + (v / this.niceMax) * (plotX1 - plotX0)
      return (v) => plotY1 - (v / this.niceMax) * (plotY1 - plotY0)
    },
    bandSize() {
      const { plotX0, plotX1, plotY0, plotY1 } = this.layout
      const n = Math.max(1, this.categories.length)
      return this.isHorizontal ? (plotY1 - plotY0) / n : (plotX1 - plotX0) / n
    },
    gridLines() {
      const { plotX0, plotX1, plotY0, plotY1 } = this.layout
      return this.ticks.map((t) => {
        const v = this.valueScaleFn(t)
        return this.isHorizontal
          ? { key: 'g' + t, x1: v, y1: plotY0, x2: v, y2: plotY1 }
          : { key: 'g' + t, x1: plotX0, y1: v, x2: plotX1, y2: v }
      })
    },
    valueTicks() {
      const { plotX0, plotY1 } = this.layout
      return this.ticks.map((t) => {
        const v = this.valueScaleFn(t)
        return this.isHorizontal
          ? { key: 'vt' + t, x: v, y: plotY1 + 16, anchor: 'middle', label: compactNumber(t) }
          : { key: 'vt' + t, x: plotX0 - 8, y: v, anchor: 'end', label: compactNumber(t) }
      })
    },
    categoryTicks() {
      const { plotX0, plotY1 } = this.layout
      return this.categories.map((c, i) => {
        const center = i * this.bandSize + this.bandSize / 2 + (this.isHorizontal ? this.layout.plotY0 : this.layout.plotX0)
        return this.isHorizontal
          ? { key: 'ct' + c, x: plotX0 - 8, y: center, anchor: 'end', baseline: 'middle', label: this.categoryLabels[i] }
          : { key: 'ct' + c, x: center, y: plotY1 + 16, anchor: 'middle', baseline: 'auto', label: this.categoryLabels[i] }
      })
    },
    valueFor() {
      return (cat, ser) => {
        const row = this.rowLookup.get(cat + '::' + (ser ?? '__single__'))
        return row ? Number(row[this.yField] || 0) : 0
      }
    },
    bars() {
      if (this.isLine) return []
      const out = []
      const grouped = this.seriesKeys.length > 1 && !this.isStacked
      this.categories.forEach((cat, i) => {
        const bandStart = i * this.bandSize + (this.isHorizontal ? this.layout.plotY0 : this.layout.plotX0)
        if (this.isStacked) {
          let cum = 0
          const barThickness = this.bandSize * 0.6
          const off = (this.bandSize - barThickness) / 2
          this.seriesKeys.forEach((ser, si) => {
            const val = this.valueFor(cat, ser)
            if (val <= 0) return
            const from = this.valueScaleFn(cum)
            const to = this.valueScaleFn(cum + val)
            cum += val
            const color = this.palette[si % this.palette.length]
            if (this.isHorizontal) {
              const y = bandStart + off
              out.push({ key: `${cat}-${ser}`, color, path: roundedRectPath(from, y, to - from, barThickness, 0, 0, 0, 0) })
            } else {
              const x = bandStart + off
              out.push({ key: `${cat}-${ser}`, color, path: roundedRectPath(x, to, barThickness, from - to, 0, 0, 0, 0) })
            }
          })
        } else if (grouped) {
          const sub = (this.bandSize * 0.7) / this.seriesKeys.length
          const groupWidth = sub * this.seriesKeys.length
          const groupOff = (this.bandSize - groupWidth) / 2
          this.seriesKeys.forEach((ser, si) => {
            const val = this.valueFor(cat, ser)
            const color = this.palette[si % this.palette.length]
            const zero = this.valueScaleFn(0)
            const v = this.valueScaleFn(val)
            if (this.isHorizontal) {
              const y = bandStart + groupOff + si * sub
              out.push({ key: `${cat}-${ser}`, color, path: roundedRectPath(zero, y, v - zero, sub * 0.85, 4, 4, 4, 4) })
            } else {
              const x = bandStart + groupOff + si * sub
              out.push({ key: `${cat}-${ser}`, color, path: roundedRectPath(x, v, sub * 0.85, zero - v, 4, 4, 0, 0) })
            }
          })
        } else {
          const val = this.valueFor(cat, this.seriesKeys[0])
          const color = this.palette[0]
          const thickness = this.bandSize * 0.6
          const off = (this.bandSize - thickness) / 2
          const zero = this.valueScaleFn(0)
          const v = this.valueScaleFn(val)
          const tl = this.styleConfig.radiusTopLeft || 0
          const tr = this.styleConfig.radiusTopRight || 0
          const br = this.styleConfig.radiusBottomRight || 0
          const bl = this.styleConfig.radiusBottomLeft || 0
          if (this.isHorizontal) {
            const y = bandStart + off
            out.push({ key: cat, color, path: roundedRectPath(zero, y, Math.max(0, v - zero), thickness, tr, tr, br, bl) })
          } else {
            const x = bandStart + off
            out.push({ key: cat, color, path: roundedRectPath(x, v, thickness, Math.max(0, zero - v), tl, tr, br, bl) })
          }
        }
      })
      return out
    },
    lineSeries() {
      if (!this.isLine) return []
      const n = this.categories.length
      const { plotX0, plotX1 } = this.layout
      const xForIndex = (i) => (n <= 1 ? (plotX0 + plotX1) / 2 : plotX0 + (i / (n - 1)) * (plotX1 - plotX0))
      const smooth = this.mergedSpec.shape === 'smooth'
      return this.seriesKeys.map((ser, si) => {
        const color = this.palette[si % this.palette.length]
        const points = this.categories.map((cat, i) => ({
          key: `${ser}-${cat}`, x: xForIndex(i), y: this.valueScaleFn(this.valueFor(cat, ser))
        }))
        return { key: ser ?? '__single__', color, points, path: smooth ? smoothPath(points) : straightPath(points) }
      })
    },
    hitAreas() {
      const { plotX0, plotY0, plotY1 } = this.layout
      return this.categories.map((cat, i) => {
        const bandStart = i * this.bandSize + (this.isHorizontal ? this.layout.plotY0 : this.layout.plotX0)
        return this.isHorizontal
          ? { key: 'h' + cat, category: cat, x: plotX0, y: bandStart, width: this.layout.plotX1 - plotX0, height: this.bandSize }
          : { key: 'h' + cat, category: cat, x: bandStart, y: plotY0, width: this.bandSize, height: plotY1 - plotY0 }
      })
    },
    legendItems() {
      if (!this.legendConfig || !this.colorField) return []
      return this.seriesKeys.map((s, i) => ({ label: s, color: this.palette[i % this.palette.length] }))
    },
    tooltip() {
      if (!this.hoverCategory || !this.categories.includes(this.hoverCategory)) return null
      const cat = this.hoverCategory
      const sampleRow = this.rowLookup.get(cat + '::' + (this.seriesKeys[0] ?? '__single__')) || {}
      const titleFn = this.tooltipConfig?.title
      const title = typeof titleFn === 'function' ? (titleFn(sampleRow) ?? cat) : cat
      const formatter = this.tooltipConfig?.items?.[0]?.valueFormatter
      const rows = this.seriesKeys.map((ser, si) => {
        const val = this.valueFor(cat, ser)
        return {
          label: ser ?? (this.tooltipConfig?.items?.[0]?.name || ''),
          value: typeof formatter === 'function' ? formatter(val) : String(val),
          color: this.palette[si % this.palette.length]
        }
      })
      const i = this.categories.indexOf(cat)
      const rawX = this.isHorizontal ? this.layout.plotX0 + 20 : (i * this.bandSize + this.bandSize / 2 + this.layout.plotX0)
      const rawY = this.isHorizontal ? (i * this.bandSize + this.bandSize / 2 + this.layout.plotY0) : this.layout.plotY0 + 8
      return {
        title,
        rows,
        x: Math.min(Math.max(0, rawX + 10), Math.max(0, this.width - 160)),
        y: Math.min(Math.max(0, rawY - 10), Math.max(0, this.layout.plotHeight - rows.length * 20 - 34))
      }
    }
  },
  watch: {
    spec: {
      deep: true,
      handler() { this.hoverCategory = ''; this.emitState() }
    }
  },
  mounted() {
    this.measure()
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => this.measure())
      this.resizeObserver.observe(this.$refs.root)
    }
    this.emitState()
  },
  beforeUnmount() {
    this.resizeObserver?.disconnect()
  },
  methods: {
    measure() {
      const w = this.$refs.root?.clientWidth
      if (w && w !== this.width) this.width = w
    },
    onMouseMove(evt) {
      const rect = evt.currentTarget.getBoundingClientRect()
      const x = evt.clientX - rect.left
      const y = evt.clientY - rect.top
      const hit = this.hitAreas.find((h) => x >= h.x && x <= h.x + h.width && y >= h.y && y <= h.y + h.height)
      this.hoverCategory = hit ? hit.category : ''
    },
    emitState() {
      try {
        void this.bars
        void this.lineSeries
        this.errorMessage = ''
        this.$emit('rendered')
      } catch (e) {
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
  display: flex;
  flex-direction: column;
}
.app-g2-chart__svg {
  display: block;
  overflow: visible;
}
.app-g2-chart__grid {
  stroke: var(--border-base, #eef2f7);
  stroke-dasharray: 3, 5;
}
.app-g2-chart__tick {
  font-size: 11px;
  fill: var(--text-tertiary, #94a3b8);
}
.app-g2-chart__tick--category {
  fill: var(--text-secondary, #4b5563);
}
.app-g2-chart__legend {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  height: 30px;
  font-size: 12px;
  color: var(--text-secondary, #4b5563);
}
.app-g2-chart__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.app-g2-chart__legend-item i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.app-g2-chart__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #94a3b8);
  font-size: var(--font-size-sm, 13px);
}
.app-g2-chart__error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 100%;
  border: 1px dashed var(--border-base, #e5e6eb);
  border-radius: var(--radius-base, 6px);
  color: var(--danger-600, #dc2626);
  background: var(--danger-50, #fef2f2);
  font-size: var(--font-size-sm, 13px);
  text-align: center;
  padding: var(--space-3, 12px);
}
.app-g2-chart__error span {
  max-width: 100%;
  color: var(--text-tertiary, #94a3b8);
  font-size: var(--font-size-xs, 12px);
  word-break: break-word;
}
.app-g2-chart__tooltip {
  position: absolute;
  z-index: 5;
  min-width: 120px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(17, 24, 39, 0.92);
  color: #fff;
  font-size: 12px;
  pointer-events: none;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
}
.app-g2-chart__tooltip-title {
  font-weight: 600;
  margin-bottom: 4px;
  opacity: 0.85;
}
.app-g2-chart__tooltip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 18px;
}
.app-g2-chart__tooltip-row i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex: 0 0 auto;
}
.app-g2-chart__tooltip-row span {
  flex: 1;
  opacity: 0.85;
}
.app-g2-chart__tooltip-row b {
  font-weight: 600;
}
</style>
