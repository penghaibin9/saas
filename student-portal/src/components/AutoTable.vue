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
            <td v-for="c in cols" :key="c.key">{{ fmt(row[c.key], c.key) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StateBlock from './StateBlock.vue'
import { localizeVisibleEnumText } from '../services/visibleEnumLocalization'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  // 可选：[{ key, label }] 显式列；不传则取第一行对象的键
  columns: { type: Array, default: null },
  title: { type: String, default: '' },
  empty: { type: String, default: '暂无数据' }
})

const list = computed(() => (Array.isArray(props.rows) ? props.rows : []).map((r) => (r && typeof r === 'object' ? r : { 值: r })))

const cols = computed(() => {
  if (props.columns && props.columns.length) return props.columns
  const first = list.value[0] || {}
  return Object.keys(first).slice(0, 8).map((k) => ({ key: k, label: k }))
})

const ENUM_FIELD_RE = /(?:status|type|node|level|mode|stage|kind|category)$/i

function fmt(v, key = '') {
  if (v == null || v === '') return '—'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (typeof v === 'object') return Array.isArray(v) ? `${v.length} 项` : JSON.stringify(v)
  const text = String(v)
  // 只在明确的状态、类型、审核节点等语义列中转换整个枚举值。
  return ENUM_FIELD_RE.test(String(key || '')) ? localizeVisibleEnumText(text) : text
}
</script>

<style scoped>
.sp-autotable { margin-top: 12px; }
.sp-autotable__title { font-size: 13px; color: #4e5969; font-weight: 600; margin: 6px 0 4px; }
</style>
