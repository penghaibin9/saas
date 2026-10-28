import { CHART_COLORS, CHART_PALETTE, baseChartSpec, compactNumber } from './chartTheme'

function safeRows(rows) {
  return Array.isArray(rows) ? rows.filter(Boolean) : []
}

export function buildBarChartSpec({
  data = [],
  xField = 'label',
  yField = 'value',
  colorField = '',
  horizontal = false,
  valueLabel = '数量',
  unit = '',
  color = CHART_COLORS.primary,
  maxLabelLength = 10
} = {}) {
  const rows = safeRows(data).map((row) => ({
    ...row,
    [xField]: String(row[xField] ?? ''),
    [yField]: Number(row[yField] || 0)
  }))
  const axis = horizontal
    ? {
        x: {
          title: false,
          labelFill: CHART_COLORS.textTertiary,
          labelFontSize: 11,
          gridStroke: CHART_COLORS.grid,
          gridLineDash: [4, 4]
        },
        y: {
          title: false,
          labelFill: CHART_COLORS.textSecondary,
          labelFontSize: 11,
          labelFormatter: (v) => (String(v).length > maxLabelLength ? `${String(v).slice(0, maxLabelLength)}...` : v)
        }
      }
    : undefined

  return baseChartSpec({
    type: 'interval',
    data: rows,
    encode: {
      x: xField,
      y: yField,
      ...(colorField ? { color: colorField } : {})
    },
    coordinate: horizontal ? { transform: [{ type: 'transpose' }] } : undefined,
    axis,
    scale: {
      color: { range: colorField ? CHART_PALETTE : [color] }
    },
    tooltip: {
      title: (d) => d?.[xField],
      items: [{ field: yField, name: valueLabel, valueFormatter: (v) => `${compactNumber(v)}${unit}` }]
    },
    style: {
      fill: colorField ? undefined : color,
      fillOpacity: 0.92,
      radiusTopLeft: 6,
      radiusTopRight: 6,
      radiusBottomLeft: horizontal ? 6 : 0,
      radiusBottomRight: horizontal ? 6 : 0
    }
  })
}

export function buildStackedBarChartSpec({
  data = [],
  xField = 'label',
  yField = 'value',
  seriesField = 'type',
  valueLabel = '数量',
  unit = '',
  horizontal = false
} = {}) {
  const rows = safeRows(data).map((row) => ({
    ...row,
    [xField]: String(row[xField] ?? ''),
    [seriesField]: String(row[seriesField] ?? ''),
    [yField]: Number(row[yField] || 0)
  }))
  return baseChartSpec({
    type: 'interval',
    data: rows,
    encode: { x: xField, y: yField, color: seriesField },
    transform: [{ type: 'stackY' }],
    coordinate: horizontal ? { transform: [{ type: 'transpose' }] } : undefined,
    legend: { color: { position: 'top' } },
    tooltip: {
      title: (d) => d?.[xField],
      items: [{ field: yField, name: valueLabel, valueFormatter: (v) => `${compactNumber(v)}${unit}` }]
    },
    style: {
      fillOpacity: 0.9,
      radiusTopLeft: 5,
      radiusTopRight: 5,
      radiusBottomLeft: horizontal ? 5 : 0,
      radiusBottomRight: horizontal ? 5 : 0
    }
  })
}

export function buildTrendChartSpec({
  data = [],
  xField = 'label',
  yField = 'value',
  seriesField = '',
  valueLabel = '数值',
  unit = '',
  smooth = true
} = {}) {
  const rows = safeRows(data).map((row) => ({
    ...row,
    [xField]: String(row[xField] ?? ''),
    [yField]: Number(row[yField] || 0)
  }))
  return baseChartSpec({
    type: 'view',
    data: rows,
    children: [
      {
        type: 'area',
        encode: { x: xField, y: yField, ...(seriesField ? { color: seriesField } : {}) },
        style: { fillOpacity: 0.12 },
        shape: smooth ? 'smooth' : 'area'
      },
      {
        type: 'line',
        encode: { x: xField, y: yField, ...(seriesField ? { color: seriesField } : {}) },
        style: { lineWidth: 2.5 },
        shape: smooth ? 'smooth' : 'line'
      },
      {
        type: 'point',
        encode: { x: xField, y: yField, ...(seriesField ? { color: seriesField } : {}) },
        style: { r: 3, lineWidth: 1.5, stroke: '#fff' }
      }
    ],
    legend: seriesField ? { color: { position: 'top' } } : false,
    tooltip: {
      title: (d) => d?.[xField],
      items: [{ field: yField, name: valueLabel, valueFormatter: (v) => `${compactNumber(v)}${unit}` }]
    }
  })
}

export function buildFunnelChartSpec({
  data = [],
  stageField = 'label',
  valueField = 'value',
  valueLabel = '人数',
  unit = '人'
} = {}) {
  const rows = safeRows(data).map((row) => ({
    ...row,
    [stageField]: String(row[stageField] ?? ''),
    [valueField]: Number(row[valueField] || 0)
  }))
  return buildBarChartSpec({
    data: rows,
    xField: stageField,
    yField: valueField,
    horizontal: true,
    valueLabel,
    unit,
    color: CHART_COLORS.info,
    maxLabelLength: 12
  })
}

export function buildDonutChartSpec({
  data = [],
  categoryField = 'label',
  valueField = 'value',
  valueLabel = '数量',
  unit = ''
} = {}) {
  const rows = safeRows(data).map((row) => ({
    ...row,
    [categoryField]: String(row[categoryField] ?? ''),
    [valueField]: Number(row[valueField] || 0)
  }))
  return baseChartSpec({
    type: 'interval',
    data: rows,
    encode: { y: valueField, color: categoryField },
    coordinate: { type: 'theta', innerRadius: 0.62 },
    transform: [{ type: 'stackY' }],
    legend: { color: { position: 'right', rowPadding: 4 } },
    axis: false,
    tooltip: {
      title: (d) => d?.[categoryField],
      items: [{ field: valueField, name: valueLabel, valueFormatter: (v) => `${compactNumber(v)}${unit}` }]
    },
    style: { stroke: '#fff', lineWidth: 2 }
  })
}
