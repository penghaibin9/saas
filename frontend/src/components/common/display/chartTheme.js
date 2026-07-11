export const CHART_COLORS = {
  primary: '#2563eb',
  primarySoft: '#60a5fa',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#06b6d4',
  violet: '#8b5cf6',
  rose: '#f43f5e',
  teal: '#14b8a6',
  amber: '#f59e0b',
  neutral: '#64748b',
  grid: '#eef2f7',
  textPrimary: '#111827',
  textSecondary: '#4b5563',
  textTertiary: '#94a3b8'
}

export const CHART_PALETTE = [
  CHART_COLORS.primary,
  CHART_COLORS.info,
  CHART_COLORS.success,
  CHART_COLORS.warning,
  CHART_COLORS.violet,
  CHART_COLORS.rose,
  CHART_COLORS.teal,
  '#64748b'
]

export function baseChartSpec(overrides = {}) {
  return {
    autoFit: true,
    padding: [18, 18, 36, 44],
    axis: {
      x: {
        title: false,
        labelFill: CHART_COLORS.textTertiary,
        labelFontSize: 11,
        labelFontWeight: 500,
        line: false,
        tick: false
      },
      y: {
        title: false,
        labelFill: CHART_COLORS.textTertiary,
        labelFontSize: 11,
        labelFontWeight: 500,
        gridStroke: CHART_COLORS.grid,
        gridLineDash: [3, 5]
      }
    },
    legend: false,
    scale: {
      color: { range: CHART_PALETTE }
    },
    interaction: {
      tooltip: {
        shared: true
      }
    },
    ...overrides
  }
}

export function compactNumber(value) {
  const n = Number(value || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n)
}
