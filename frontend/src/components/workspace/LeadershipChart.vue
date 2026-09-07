<template><div ref="host" class="leadership-chart" role="img" :aria-label="label + (value === null && kind === 'ring' ? '：暂不可用' : '')" /></template>
<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { init, use, graphic } from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, GraphicComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([PieChart, BarChart, GridComponent, TooltipComponent, GraphicComponent, AriaComponent, CanvasRenderer])
const props = defineProps({ kind: { type: String, default: 'ring' }, label: { type: String, required: true }, value: { type: Number, default: null }, rows: { type: Array, default: () => [] }, color: { type: String, default: '#46dce1' } })
const host = ref(null)
let chart, observer
function render() {
  if (!chart) return
  const animated = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const base = { backgroundColor: 'transparent', animation: animated, animationDuration: 900, aria: { enabled: true }, tooltip: { trigger: 'item', renderMode: 'richText' } }
  const valid = props.value !== null && Number.isFinite(props.value) && props.value >= 0 && props.value <= 100
  const option = props.kind === 'ring' ? {
    ...base,
    graphic: [{ type: 'text', left: 'center', top: '39%', style: { text: valid ? props.value + '%' : '—', fill: '#e3faff', font: '600 32px sans-serif', textAlign: 'center' } }, { type: 'text', left: 'center', top: '59%', style: { text: props.label, fill: '#91b3d0', font: '12px sans-serif', textAlign: 'center' } }],
    series: [{ type: 'pie', radius: ['72%', '81%'], center: ['50%', '50%'], silent: !valid, label: { show: false }, emphasis: { scale: false }, data: [{ name: props.label, value: valid ? props.value : 0, itemStyle: { color: props.color, borderRadius: 5, shadowBlur: 16, shadowColor: props.color + '55' } }, { name: '其余占比', value: valid ? 100 - props.value : 100, itemStyle: { color: '#193450' }, tooltip: { show: false } }] }]
  } : {
    ...base, grid: { left: 3, right: 25, top: 12, bottom: 0, containLabel: true },
    xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#1e3650' } }, axisLabel: { color: '#7196b7', fontSize: 10 } },
    yAxis: { type: 'category', inverse: true, data: props.rows.map(row => row.label), axisLabel: { color: '#a6c4dc', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 9, showBackground: true, backgroundStyle: { color: '#122e48' }, label: { show: true, position: 'right', color: '#d8f4ff', formatter: p => p.value === null || p.value === undefined ? '—' : p.value }, data: props.rows.map(row => row.value), itemStyle: { borderRadius: 4, color: new graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#245791' }, { offset: 1, color: props.color }]) } }]
  }
  chart.setOption(option, true)
}
watch(() => [props.value, props.rows, props.kind, props.color], render, { deep: true })
onMounted(() => { chart = init(host.value, null, { renderer: 'canvas' }); observer = new ResizeObserver(() => chart.resize()); observer.observe(host.value); render() })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<style scoped>.leadership-chart{width:100%;height:190px;min-width:0}</style>
