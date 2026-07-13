<template>
  <ModulePageShell title="分配日志" subtitle="岗位分配、退岗与指导教师调整的不可变审计台账" role-name="指导教师 / 管理员" :data-scope-name="scopeHint">
    <div class="bar"><AppSearchBox v-model="keyword" placeholder="按学生、学号或操作人搜索" @search="reload" /></div>
    <div v-if="error" class="state is-err">{{ error }} <button class="mp-link" @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading" :pagination="pagination" @page-change="onPageChange">
      <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.studentName }}</div><div class="mp-cell-sub">{{ row.studentNo }}</div></template>
      <template #cell-action="{ row }"><AppStatusTag :type="row.action === 'UNASSIGN_POSITION' ? 'warning' : 'info'">{{ actionLabel(row.action) }}</AppStatusTag></template>
      <template #cell-detail="{ row }"><span class="detail">{{ detailText(row) }}</span></template>
      <template #cell-actions="{ row }"><button class="mp-link" @click="$router.push('/admin/internship/students/' + row.recordId)">查看档案</button></template>
    </DataTable>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppSearchBox, AppStatusTag } from '@/components/common'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'

const ACTIONS = { ASSIGN_ADVISOR: '分配指导教师', ASSIGN_POSITION: '分配岗位', UNASSIGN_POSITION: '退岗' }
export default {
  name: 'AssignmentLogView', components: { ModulePageShell, DataTable, AppSearchBox, AppStatusTag },
  data() { return { rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '', keyword: '', scopeHint: '指导教师仅可查看本人范围内学生的分配记录', columns: [
    { key: 'student', title: '学生', width: '150px' }, { key: 'action', title: '动作', width: '130px' },
    { key: 'detail', title: '变更内容' }, { key: 'operator', title: '操作人', width: '110px' },
    { key: 'occurredAt', title: '操作时间', width: '160px' }, { key: 'actions', title: '操作', width: '90px' }
  ] } },
  computed: { pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } } },
  created() { this.load() },
  methods: {
    actionLabel(value) { return ACTIONS[value] || value },
    detailText(row) { const d = row.detail || {}; return d.title || d.reason || (d.toUserId ? `调整至教职工账号 ${d.toUserId}` : '—') },
    reload() { this.page = 1; this.load() }, onPageChange(page) { this.page = page; this.load() },
    async load() { this.loading = true; this.error = ''; const res = await internStudentApi.getAssignmentLogs({ page: this.page, pageSize: this.pageSize, keyword: this.keyword }); this.loading = false; if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else { this.error = res.message; this.rows = []; this.total = 0 } }
  }
}
</script>

<style scoped>.bar { margin-bottom: var(--space-3); }.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); }.state.is-err { color: var(--danger-600); }.detail { color: var(--text-secondary); font-size: var(--font-size-sm); }</style>
