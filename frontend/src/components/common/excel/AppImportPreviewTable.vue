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
import { safeBusinessMessage } from '@/utils/presentationSafety'

const COMMON_FIELD_LABELS = Object.freeze({
  studentNo: '学号', studentName: '姓名', realName: '姓名', teacherNo: '工号', teacherName: '教师姓名',
  className: '班级', batchNo: '批次编号', batchName: '批次名称', topicNo: '课题编号', topicTitle: '课题名称',
  title: '名称', company: '企业', companyName: '企业', enterpriseName: '企业', advisorName: '指导教师',
  mentorType: '导师类型', projectName: '项目名称', projectType: '项目类型', schoolYear: '学年',
  usualScore: '平时成绩', midtermScore: '期中成绩', finalScore: '期末成绩', initialStatus: '初始状态',
  exceptionFlag: '异常标记', status: '状态', sourceType: '来源类型', submitReview: '提交审核',
  capacity: '容量', maxCapacity: '最大容量', creditCode: '统一社会信用代码', industry: '行业',
  region: '地区', location: '地点', city: '城市', contactPerson: '联系人', major: '专业',
  headcount: '需求人数', note: '备注', choiceOrder: '志愿顺序'
})

/**
 * AppImportPreviewTable — 预校验行级预览（通过/失败逐行展示）。
 * Props:
 *  - rows: 原始行 list[dict]
 *  - errors: [{ rowNo, field, message }]（rowNo 为数据行 1-based）
 *  - previewSchema: [{ key, label, formatter?, sensitive? }] 正式展示契约
 *  - previewFields: 兼容旧调用的字段 key 列表
 */
export default {
  name: 'AppImportPreviewTable',
  props: {
    rows: { type: Array, default: () => [] },
    errors: { type: Array, default: () => [] },
    previewFields: { type: Array, default: () => [] },
    previewSchema: { type: Array, default: () => [] }
  },
  computed: {
    errMap() {
      const m = {}
      for (const e of this.errors || []) {
        const n = e.rowNo
        const fieldLabel = this.fieldLabels[e.fieldCode || e.field] || ''
        const message = safeBusinessMessage(e.message, '该字段校验未通过')
        m[n] = (m[n] ? `${m[n]}；` : '') + (fieldLabel ? `${fieldLabel}：${message}` : message)
      }
      return m
    },
    schema() {
      if (this.previewSchema.length) return this.previewSchema
      return this.previewFields.map((key) => ({ key, label: COMMON_FIELD_LABELS[key] || '业务字段' }))
    },
    fieldLabels() {
      return Object.fromEntries(this.schema.map((field) => [field.key, field.label || '业务字段']))
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
      if (!this.schema.length) {
        return '该行已读取，请查看校验结果'
      }
      const values = this.schema.map((field) => {
        const value = r?.[field.key]
        if (value === undefined || value === null || value === '') return ''
        if (field.sensitive) return `${field.label || '敏感信息'}已填写`
        if (typeof field.formatter === 'function') return field.formatter(value, r)
        if (typeof value === 'object') return Array.isArray(value) ? `${value.length} 项` : '详细信息已收起'
        return String(value)
      }).filter(Boolean)
      return values.join(' / ') || '该行已读取，请查看校验结果'
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
