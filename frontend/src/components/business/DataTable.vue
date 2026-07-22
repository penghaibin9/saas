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
            :class="[{ 'is-clickable': rowClickable, 'is-selected': isSelected(row) }, rowClassOf(row)]"
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
      <AppPagination
        :total="pagination.total"
        :page="pagination.page"
        :page-size="pagination.pageSize"
        :show-size-changer="showSizeChanger"
        @change="onPagerChange"
      />
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
 *  - rowClass: 逐行 class（String 或 (row)=>String）——供业务页按行状态上色等，组件不含业务假设；
 *              业务页用 :deep(.你的类名) 定义样式。默认空，向后兼容。
 *  - pagination: { page, pageSize, total } | null
 *  - showSizeChanger: 是否显示「每页条数」下拉（默认关闭——现有消费页的 page-change 处理函数
 *    只接收页码，不处理 pageSize 变化；默认打开会出现「能点但不生效」的假控件，按页迁移时再开）
 * Slots: cell-<key>（作用域 { row }）、batch-actions（作用域 { keys }）
 * Emits: update:selected / row-click / page-change（页码 number，向后兼容既有 onPageChange(page) 消费方）
 */
import { AppPagination } from '@/components/common'

export default {
  name: 'DataTable',
  components: { AppPagination },
  props: {
    columns: { type: Array, required: true },
    rows: { type: Array, default: () => [] },
    rowKey: { type: String, default: 'id' },
    selectable: { type: Boolean, default: false },
    selected: { type: Array, default: () => [] },
    rowClickable: { type: Boolean, default: false },
    rowClass: { type: [Function, String], default: '' },
    pagination: { type: Object, default: null },
    showSizeChanger: { type: Boolean, default: false }
  },
  emits: ['update:selected', 'row-click', 'page-change'],
  computed: {
    selectedKeys() {
      return this.selected
    },
    allChecked() {
      return this.rows.length > 0 && this.rows.every((r) => this.selectedKeys.includes(r[this.rowKey]))
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
    },
    rowClassOf(row) {
      return typeof this.rowClass === 'function' ? (this.rowClass(row) || '') : this.rowClass
    },
    isSelected(row) {
      return this.selectable && this.selectedKeys.includes(row[this.rowKey])
    },
    onPagerChange({ page }) {
      this.$emit('page-change', page)
    }
  }
}
</script>

<style scoped>
/* 市场对标精修（表头=A 淡渐变有分量，行体/悬浮/选中/分页=A+ 克制企业风）。
 * 全站共享，改这一处，教务/实习/毕设/学工等所有消费页一起生效。 */
.dt {
  background: #fff;
  border: 1px solid var(--card-b);
  border-radius: 12px;
  box-shadow:
    0 1px 2px rgba(15, 40, 90, 0.04),
    0 14px 36px -22px rgba(23, 58, 138, 0.22);
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
/* 表头 = A：淡渐变 + 字距 + 稍深字色；叠加吸顶 + 滚动浅阴影（长表格场景） */
.dt__th {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 14px 18px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--t2);
  letter-spacing: 0.04em;
  background: linear-gradient(180deg, #fbfdff, var(--bg-section));
  border-bottom: 1px solid var(--dv);
  white-space: nowrap;
  box-shadow: 0 1px 0 rgba(15, 40, 90, 0.04);
}
.dt__th:first-child {
  padding-left: 20px;
}
/* 行体 = A+：发丝分行 + 大留白 + 数字等宽 + 中性淡灰悬浮 */
.dt__td {
  padding: 15px 18px;
  font-size: var(--font-size-base);
  color: var(--t2);
  border-bottom: 1px solid #f1f4fa;
  vertical-align: middle;
  font-variant-numeric: var(--font-numeric);
  transition: background 0.1s;
}
.dt__td:first-child {
  padding-left: 20px;
}
.dt__tr:last-child .dt__td {
  border-bottom: none;
}
.dt__tr.is-clickable {
  cursor: pointer;
}
.dt__tr:hover .dt__td {
  background: #f7f9fd;
}
/* 选中行：品牌淡蓝 + 左侧强调条（勾选批量 / 业务页高亮当前行时用） */
.dt__tr.is-selected .dt__td {
  background: var(--pri-bg);
}
.dt__tr.is-selected .dt__td:first-child {
  box-shadow: inset 3px 0 0 var(--pri);
}
.dt__th--check,
.dt__td--check {
  width: 36px;
  text-align: center;
}
.dt__pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 12px 18px;
  border-top: 1px solid #eef2f8;
}
</style>
