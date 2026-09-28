<template>
  <span class="app-dd" :class="'is-' + tone" :title="titleText">
    <span class="app-dd__text">{{ text }}</span>
    <span v-if="badge" class="app-dd__badge">{{ badge }}</span>
  </span>
</template>

<script>
/**
 * AppDateDisplay — 日期/截止展示。
 * 空值 → 未设置；截止语义 → 今天截止 / 明天截止 / 剩余 N 天 / 已逾期 / 已归档 / 已完成。
 * 禁止页面直接渲染 undefined / null / Invalid Date。
 */
import {
  formatSafeDisplay,
  getDeadlineMeta,
  formatDate,
  formatDateTime,
  isEmptyDate
} from '@/utils/dateUtils'

export default {
  name: 'AppDateDisplay',
  props: {
    value: { type: [String, Date, Number], default: '' },
    /** date | datetime | deadline */
    mode: { type: String, default: 'date' },
    emptyText: { type: String, default: '未设置' },
    status: { type: String, default: '' },
    archived: { type: Boolean, default: false },
    completed: { type: Boolean, default: false },
    /** deadline 模式是否附加原始日期 */
    showRaw: { type: Boolean, default: true }
  },
  computed: {
    meta() {
      if (this.mode !== 'deadline') return null
      return getDeadlineMeta(this.value, {
        status: this.status,
        archived: this.archived,
        completed: this.completed
      })
    },
    text() {
      if (this.mode === 'deadline') {
        const m = this.meta
        if (!m || m.kind === 'empty') return this.emptyText
        if (m.kind === 'archived' || m.kind === 'completed') return m.label
        if (!this.showRaw) return m.label
        const raw = formatDateTime(this.value, '') || formatDate(this.value, '')
        if (m.kind === 'overdue' || m.kind === 'today' || m.kind === 'tomorrow' || m.kind === 'remain') {
          return raw ? `${raw}（${m.label}）` : m.label
        }
        return raw || m.label
      }
      if (isEmptyDate(this.value)) return this.emptyText
      return formatSafeDisplay(this.value, {
        withTime: this.mode === 'datetime',
        empty: this.emptyText
      })
    },
    badge() {
      if (this.mode !== 'deadline' || !this.meta) return ''
      const k = this.meta.kind
      if (k === 'overdue' || k === 'today' || k === 'tomorrow' || k === 'remain') {
        // 已在 text 中带括号时不再重复 badge；keep empty unless showRaw=false
        return this.showRaw ? '' : this.meta.label
      }
      return ''
    },
    tone() {
      if (this.mode === 'deadline' && this.meta) {
        return this.meta.tone || 'default'
      }
      if (isEmptyDate(this.value)) return 'muted'
      return 'default'
    },
    titleText() {
      if (isEmptyDate(this.value)) return this.emptyText
      return formatDateTime(this.value, '') || formatDate(this.value, '')
    }
  }
}
</script>

<style scoped>
.app-dd {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-sm, 13px);
  color: var(--text-primary, #0f172a);
}
.app-dd.is-muted { color: var(--text-tertiary, #94a3b8); }
.app-dd.is-danger { color: var(--danger-600, #dc2626); font-weight: 500; }
.app-dd.is-warning { color: var(--warning-700, #b45309); }
.app-dd.is-success { color: var(--success-700, #15803d); }
.app-dd.is-info { color: var(--text-secondary, #64748b); }
.app-dd.is-primary { color: var(--primary-700, #1d4ed8); }
.app-dd__badge {
  font-size: 11px;
  padding: 0 6px;
  height: 18px;
  line-height: 18px;
  border-radius: 999px;
  background: var(--gray-100, #f1f5f9);
  color: inherit;
}
</style>
