<template>
  <div class="dt">
    <div v-if="selectable && selectedKeys.length" class="dt__batch">
      <span class="dt__batch-count">已选 {{ selectedKeys.length }} 条</span>
      <slot name="batch-actions" :keys="selectedKeys" />
      <button type="button" class="dt__batch-clear" @click="clearSelection">取消选择</button>
    </div>
    <div class="dt__scroll">
      <table class="dt__table">
        <thead>
          <tr>
            <th v-if="selectable" class="dt__th dt__th--check">
              <input type="checkbox" :checked="allChecked" @change="toggleAll($event.target.checked)" />
            </th>
            <th
              v-for="c in columns"
              :key="c.key"
              class="dt__th"
              :style="{ width: c.width, textAlign: c.align || 'left' }"
            >
              {{ c.title }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row[rowKey]"
            class="dt__tr"
            :class="{ 'is-clickable': rowClickable }"
            @click="rowClickable && $emit('row-click', row)"
          >
            <td v-if="selectable" class="dt__td dt__td--check" @click.stop>
              <input
                type="checkbox"
                :checked="selectedKeys.includes(row[rowKey])"
                @change="toggleRow(row[rowKey], $event.target.checked)"
              />
            </td>
            <td
              v-for="c in columns"
              :key="c.key"
              class="dt__td"
              :style="{ textAlign: c.align || 'left' }"
              @click="c.key === 'actions' ? $event.stopPropagation() : null"
            >
              <slot :name="'cell-' + c.key" :row="row">{{ row[c.key] ?? '—' }}</slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="pagination" class="dt__pager">
      <span class="dt__pager-info">
        共 {{ pagination.total }} 条 · 第 {{ pagination.page }} / {{ maxPage }} 页
      </span>
      <div class="dt__pager-ops">
        <AppButton variant="ghost" :disabled="pagination.page <= 1" @click="$emit('page-change', pagination.page - 1)">上一页</AppButton>
        <AppButton variant="ghost" :disabled="pagination.page >= maxPage" @click="$emit('page-change', pagination.page + 1)">下一页</AppButton>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * DataTable — 通用业务数据表（不含任何业务字段假设）。
 * Props:
 *  - columns: [{ key, title, width?, align? }]（key='actions' 的列点击不冒泡行点击）
 *  - rows: 行数据数组
 *  - rowKey: 行主键字段名（默认 'id'）
 *  - selectable: 是否显示勾选列（配合 #batch-actions 插槽形成批量条）
 *  - selected: 受控选中 key 数组（v-model:selected）
 *  - rowClickable: 行是否可点击（emits row-click）
 *  - pagination: { page, pageSize, total } | null
 * Slots: cell-<key>（作用域 { row }）、batch-actions（作用域 { keys }）
 * Emits: update:selected / row-click / page-change
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'DataTable',
  components: { AppButton },
  props: {
    columns: { type: Array, required: true },
    rows: { type: Array, default: () => [] },
    rowKey: { type: String, default: 'id' },
    selectable: { type: Boolean, default: false },
    selected: { type: Array, default: () => [] },
    rowClickable: { type: Boolean, default: false },
    pagination: { type: Object, default: null }
  },
  emits: ['update:selected', 'row-click', 'page-change'],
  computed: {
    selectedKeys() {
      return this.selected
    },
    allChecked() {
      return this.rows.length > 0 && this.rows.every((r) => this.selectedKeys.includes(r[this.rowKey]))
    },
    maxPage() {
      if (!this.pagination) return 1
      return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
    }
  },
  methods: {
    toggleAll(checked) {
      this.$emit('update:selected', checked ? this.rows.map((r) => r[this.rowKey]) : [])
    },
    toggleRow(key, checked) {
      const next = checked ? [...this.selectedKeys, key] : this.selectedKeys.filter((k) => k !== key)
      this.$emit('update:selected', next)
    },
    clearSelection() {
      this.$emit('update:selected', [])
    }
  }
}
</script>

<style scoped>
/* 母版 .tbl 数据表：玻璃卡容器 + 淡蓝表头 + 行 hover */
.dt {
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: var(--r);
  box-shadow: var(--s1);
  overflow: hidden;
  transition:
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}
.dt:hover {
  box-shadow: var(--s2);
}
.dt__batch {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-2) var(--space-4);
  background: var(--bg-batchbar);
  border-bottom: 1px solid var(--bg-batchbar);
  font-size: var(--font-size-sm);
  color: #fff;
}
.dt__batch :deep(.mp-link) {
  color: #bfdbfe;
}
.dt__batch :deep(.mp-link.is-disabled) {
  color: rgba(255, 255, 255, 0.35);
}
.dt__batch-count {
  font-weight: var(--font-weight-semibold);
}
.dt__batch-clear {
  margin-left: auto;
  border: none;
  background: none;
  color: rgba(255, 255, 255, 0.65);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.dt__batch-clear:hover {
  color: #fff;
}
.dt__scroll {
  overflow-x: auto;
}
.dt__table {
  width: 100%;
  border-collapse: collapse;
}
.dt__th {
  padding: 10px 14px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--t3);
  background: var(--bg-section);
  border-bottom: 1px solid var(--dv);
  white-space: nowrap;
}
.dt__td {
  padding: 11px 14px;
  font-size: var(--font-size-base);
  border-bottom: 1px solid var(--dv);
  vertical-align: middle;
  transition: background 0.1s;
}
.dt__tr:last-child .dt__td {
  border-bottom: none;
}
.dt__tr.is-clickable {
  cursor: pointer;
}
.dt__tr.is-clickable:hover .dt__td {
  background: var(--bg-hover);
}
.dt__th--check,
.dt__td--check {
  width: 36px;
  text-align: center;
}
.dt__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-4);
  border-top: 1px solid var(--dv);
  font-size: var(--font-size-sm);
  color: var(--t3);
}
.dt__pager-info {
  font-variant-numeric: var(--font-numeric);
}
.dt__pager-ops {
  display: flex;
  gap: var(--space-2);
}
</style>
