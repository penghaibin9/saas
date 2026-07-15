<template>
  <ModulePageShell
    title="成绩操作审计"
    subtitle="成绩录入/提交/审核/发布/退回/归档/更正与成绩单导出全链路操作留痕：教务处/学院可查全量，任课教师仅可自查本人操作"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter-row">
        <select v-model="bizType" class="aa-input" @change="onFilterChange">
          <option value="">全部对象</option>
          <option value="AA_GRADE_TASK">成绩任务（录入/提交/审核/发布/退回/归档）</option>
          <option value="AA_GRADE_RECORD">成绩明细更正</option>
          <option value="AA_GRADE_TRANSCRIPT">成绩单导出</option>
        </select>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无匹配的操作记录" description="成绩相关操作发生后会记入这里" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-bizType="{ row }">{{ bizTypeLabel(row.bizType) }}</template>
        <template #cell-action="{ row }">{{ actionLabel(row.action) }}</template>
        <template #cell-occurredAt="{ row }">{{ formatTime(row.occurredAt) }}</template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 成绩操作审计（/admin/academic-affairs/grade-audit，08 号补建三级卡之一）。
 * 只读，复用 GET /grade-views/audit（新增，读 t_affairs_audit_trail，biz_type=AA_GRADE_*，
 * 数据来自成绩模块既有 _audit() 写入，非新表）。数据范围由后端裁定：
 * ACADEMIC_ADMIN/SCHOOL_ADMIN/COLLEGE_ADMIN 查全量，ACADEMIC_TEACHER 仅本人操作，其余角色 403。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const BIZ_TYPE_LABEL = {
  AA_GRADE_TASK: '成绩任务', AA_GRADE_RECORD: '成绩明细/更正', AA_GRADE_TRANSCRIPT: '成绩单导出'
}
const ACTION_LABEL = {
  CREATE: '创建任务', ENTER: '录入成绩', IMPORT: '批量导入', SUBMIT: '提交学院审核',
  COLLEGE_RETURN: '学院退回', COLLEGE_APPROVE: '学院通过', PUBLISH: '教务发布',
  ACADEMIC_RETURN: '教务退回', ARCHIVE: '学期归档',
  CHANGE_APPLY: '发起更正申请', CHANGE_STEP: '更正流转', CHANGE_APPROVE: '更正终审通过', CHANGE_REJECT: '更正驳回',
  EXPORT: '导出成绩单'
}

export default {
  name: 'AaGradeAuditView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      bizType: '',
      loading: true, error: '', rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'occurredAt', title: '时间' },
        { key: 'bizType', title: '对象' },
        { key: 'action', title: '动作' },
        { key: 'operator', title: '操作人' },
        { key: 'roleName', title: '角色' },
        { key: 'detail', title: '说明' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    bizTypeLabel(v) { return BIZ_TYPE_LABEL[v] || v },
    actionLabel(v) { return ACTION_LABEL[v] || v },
    formatTime(v) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' },
    onFilterChange() { this.pagination.page = 1; this.load() },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradeAudit({
        bizType: this.bizType || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter-row { margin-bottom: 12px; }
.aa-input {
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border-300, #d0d3d9);
  border-radius: 6px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #1f2329);
  font-size: 14px;
}
</style>
