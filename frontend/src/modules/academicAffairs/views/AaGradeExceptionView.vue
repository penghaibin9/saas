<template>
  <ModulePageShell
    title="成绩异常"
    subtitle="缺考 / 缓考 / 免修标记学生汇总（跨录入任务），可下钻到学生成绩单"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-fail')">挂科清单</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">学期<input v-model.trim="term" class="aa-input aa-input--sm" placeholder="学期码（空=全部）" @keyup.enter="search" /></label>
        <label class="aa-filter__item">
          异常类型
          <select v-model="exceptionFlag" class="aa-select" @change="search">
            <option value="">全部</option>
            <option v-for="(label, val) in EXCEPTION_FLAG_LABEL" :key="val" :value="val">{{ label }}</option>
          </select>
        </label>
        <button class="mp-btn" @click="search">查询</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="无成绩异常记录" description="当前范围内没有缺考/缓考/免修标记的学生" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="recordId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-exceptionFlag="{ row }">
          <AppStatusTag :type="exceptionFlagColor(row.exceptionFlag)">{{ EXCEPTION_FLAG_LABEL[row.exceptionFlag] || row.exceptionFlag }}</AppStatusTag>
        </template>
        <template #cell-taskStatus="{ row }">
          <AppStatusTag :type="taskStatusColor(row.taskStatus)">{{ TASK_STATUS_LABEL[row.taskStatus] || row.taskStatus }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :disabled="!row.studentId" @click="goTranscript(row)">成绩单</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩异常（/admin/academic-affairs/grade-exception）：GET /grade-views/exception-list。
 * 汇总各录入任务中 exception_flag ∈ {ABSENT/DEFERRED/EXEMPT} 的学生（跨任务读侧下钻，零写入）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { EXCEPTION_FLAG_LABEL, exceptionFlagColor } from '@/modules/academicAffairs/constants/grade-graduation'

const TASK_STATUS_LABEL = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务终审中', PUBLISHED: '已发布',
  RETURNED: '已退回', ARCHIVED: '已归档'
}

export default {
  name: 'AaGradeExceptionView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], term: '', exceptionFlag: '',
      pagination: { page: 1, pageSize: 50, total: 0 },
      EXCEPTION_FLAG_LABEL, TASK_STATUS_LABEL,
      columns: [
        { key: 'studentName', title: '学生' },
        { key: 'studentNo', title: '学号' },
        { key: 'courseName', title: '课程' },
        { key: 'term', title: '学期' },
        { key: 'exceptionFlag', title: '异常类型' },
        { key: 'taskStatus', title: '任务状态' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    exceptionFlagColor,
    taskStatusColor(s) {
      if (s === 'PUBLISHED') return 'success'
      if (s === 'RETURNED') return 'danger'
      if (['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(s)) return 'processing'
      return 'default'
    },
    goTranscript(row) {
      this.$router.push({ path: '/admin/academic-affairs/transcript', query: { studentId: row.studentId, name: row.studentName } })
    },
    onPageChange(p) { this.pagination.page = p; this.load() },
    search() { this.pagination.page = 1; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getExceptionList({
        term: this.term || undefined,
        exceptionFlag: this.exceptionFlag || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 200px; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
</style>
