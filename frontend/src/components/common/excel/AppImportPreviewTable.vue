<template>
  <div class="aipt">
    <table class="aipt__table">
      <thead>
        <tr><th>行号</th><th>数据预览</th><th>校验结果</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in previewRows" :key="r.row" :class="{ 'is-invalid': !r.valid }">
          <td>{{ r.row }}</td>
          <td>{{ r.data }}</td>
          <td>
            <span v-if="r.valid" class="aipt__ok">通过</span>
            <span v-else class="aipt__fail">{{ r.error }}</span>
          </td>
        </tr>
        <tr v-if="!previewRows.length">
          <td colspan="3" class="aipt__empty">暂无数据</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
/**
 * AppImportPreviewTable — 预校验行级预览（通过/失败逐行展示）。
 * Props:
 *  - rows: 原始行 list[dict]
 *  - errors: [{ rowNo, field, message }]（rowNo 为数据行 1-based）
 *  - previewFields: 用于拼接「数据预览」的字段 key 列表（缺省取行前 3 个非空字段）
 */
export default {
  name: 'AppImportPreviewTable',
  props: {
    rows: { type: Array, default: () => [] },
    errors: { type: Array, default: () => [] },
    previewFields: { type: Array, default: () => [] }
  },
  computed: {
    errMap() {
      const m = {}
      for (const e of this.errors || []) {
        const n = e.rowNo
        m[n] = (m[n] ? `${m[n]}；` : '') + (e.message || '')
      }
      return m
    },
    previewRows() {
      return (this.rows || []).map((r, i) => {
        const rowNo = i + 1
        const err = this.errMap[rowNo]
        return { row: rowNo, data: this._preview(r), valid: !err, error: err || '' }
      })
    }
  },
  methods: {
    _preview(r) {
      if (this.previewFields.length) {
        return this.previewFields.map((k) => r[k]).filter((v) => v !== undefined && v !== '').join(' / ')
      }
      const vals = Object.values(r).filter((v) => v !== undefined && v !== null && v !== '')
      return vals.slice(0, 3).join(' / ') || JSON.stringify(r)
    }
  }
}
</script>

<style scoped>
.aipt {
  max-height: 42vh;
  overflow-y: auto;
}
.aipt__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-xs);
}
.aipt__table th,
.aipt__table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--border-light);
  text-align: left;
}
.aipt__table tr.is-invalid td {
  background: var(--danger-50);
}
.aipt__ok {
  color: var(--success-600);
}
.aipt__fail {
  color: var(--danger-600);
}
.aipt__empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--space-5);
}
</style>
