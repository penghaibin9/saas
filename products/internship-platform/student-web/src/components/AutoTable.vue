<template>
  <div class="sp-autotable">
    <div v-if="title" class="sp-autotable__title">{{ title }}</div>
    <StateBlock v-if="!list.length" type="empty" :text="empty" />
    <div v-else class="sp-table-wrap">
      <table class="sp-table">
        <thead>
          <tr><th v-for="c in cols" :key="c.key">{{ c.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in list" :key="ri">
            <td v-for="c in cols" :key="c.key">{{ fmt(row[c.key], c, row) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StateBlock from './StateBlock.vue'
import { safeVisibleEnumLabel } from '../services/visibleEnumLocalization'

let warnedMissingColumns = false

const props = defineProps({
  rows: { type: Array, default: () => [] },
  // 正式表格必须显式声明 [{ key, label, formatter? }]，禁止由接口 key 推导用户表头。
  columns: { type: Array, default: null },
  title: { type: String, default: '' },
  empty: { type: String, default: '暂无数据' }
})

const list = computed(() => (Array.isArray(props.rows) ? props.rows : []).map((r) => (r && typeof r === 'object' ? r : { 值: r })))

const cols = computed(() => {
  if (props.columns && props.columns.length) {
    return props.columns.map((column) => ({
      ...column,
      label: column.label || '未命名字段'
    }))
  }
  if (!warnedMissingColumns && typeof console !== 'undefined') {
    warnedMissingColumns = true
    console.warn('[AutoTable] 正式表格缺少 columns 展示契约')
  }
  return [{ key: '__safeSummary', label: '数据摘要', unconfigured: true }]
})

const ENUM_FIELD_RE = /(?:status|type|node|level|mode|stage|kind|category)$/i

function fmt(v, column = {}, row = {}) {
  if (column.unconfigured) return Object.keys(row).length ? '该记录已读取' : '—'
  if (typeof column.formatter === 'function') return column.formatter(v, row)
  if (v == null || v === '') return '—'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (typeof v === 'object') return Array.isArray(v) ? `${v.length} 项` : '详细信息已收起'
  const text = String(v)
  // 只在明确的状态、类型、审核节点等语义列中转换整个枚举值；同码跨域时再带上字段+表头上下文。
  const contextKey = `${column.key || ''}:${column.label || ''}`
  return ENUM_FIELD_RE.test(String(column.key || '')) ? safeVisibleEnumLabel(text, '状态待确认', contextKey) : text
}
</script>

<style scoped>
.sp-autotable { margin-top: 12px; }
.sp-autotable__title { font-size: 13px; color: #4e5969; font-weight: 600; margin: 6px 0 4px; }
</style>
