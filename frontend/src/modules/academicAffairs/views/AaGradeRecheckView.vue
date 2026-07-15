<template>
  <ModulePageShell
    title="成绩复核"
    subtitle="按任务复核已录入/在审/已发布成绩的明细：逐生核对分数、及格结果与更正留痕，本页不修改任何数据"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="选择成绩录入任务">
        <div class="aa-filter-row">
          <select v-model="statusFilter" class="aa-input" @change="onFilterChange">
            <option value="">全部状态</option>
            <option value="NOT_STARTED">未开始</option>
            <option value="INPUTTING">录入中</option>
            <option value="SUBMITTED">待学院审核</option>
            <option value="ACADEMIC_REVIEW">待教务终审</option>
            <option value="PUBLISHED">已发布</option>
            <option value="RETURNED">已退回</option>
            <option value="ARCHIVED">已归档</option>
          </select>
        </div>
        <ErrorState v-if="taskError" :description="taskError" @retry="loadTasks" />
        <LoadingState v-else-if="taskLoading" />
        <EmptyState v-else-if="!taskRows.length" title="暂无匹配任务" description="任课教师建立成绩录入任务后会出现在这里" />
        <DataTable
          v-else
          :columns="taskColumns"
          :rows="taskRows"
          row-key="gradeTaskId"
          :pagination="taskPagination"
          @page-change="onTaskPageChange"
        >
          <template #cell-status="{ row }">
            <AppStatusTag type="primary" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-btn mp-btn--sm" :class="{ 'mp-btn--primary': activeTask && activeTask.gradeTaskId === row.gradeTaskId }" @click="loadRecords(row)">
              复核明细
            </button>
          </template>
        </DataTable>
      </AppSectionCard>

      <AppSectionCard v-if="activeTask" :title="`成绩明细复核 · ${activeTask.courseName || '（未命名课程）'}（任务ID ${activeTask.gradeTaskId}）`">
        <ErrorState v-if="recordError" :description="recordError" @retry="() => loadRecords(activeTask)" />
        <LoadingState v-else-if="recordLoading" />
        <EmptyState v-else-if="!recordRows.length" title="该任务暂无成绩明细" description="任课教师尚未录入分数" />
        <DataTable v-else :columns="recordColumns" :rows="recordRows" row-key="recordId">
          <template #cell-passStatus="{ row }">
            <AppStatusTag v-if="row.passStatus" :type="row.passStatus === 'PASSED' ? 'success' : 'danger'" dot>
              {{ row.passStatus === 'PASSED' ? '及格' : '不及格' }}
            </AppStatusTag>
            <span v-else>—</span>
          </template>
          <template #cell-exceptionFlag="{ row }">{{ exceptionLabel(row.exceptionFlag) }}</template>
          <template #cell-source="{ row }">{{ sourceLabel(row.source) }}</template>
          <template #cell-prevTotalScore="{ row }">{{ row.prevTotalScore != null ? row.prevTotalScore : '—' }}</template>
          <template #cell-changeAt="{ row }">{{ formatTime(row.changeAt) }}</template>
        </DataTable>
        <p class="mp-note">
          仅供核对，不在本页修改成绩；如确认分数有误，请到「成绩更正」页填写任务ID / 记录ID（见上表首列）发起更正申请。
        </p>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 成绩复核（/admin/academic-affairs/grade-recheck，08 号补建三级卡之一）。
 * 只读核对任务成绩明细，不新增写接口：
 *  - 任务列表复用 GET /grade-tasks（已实现）；
 *  - 明细复用 GET /grade-tasks/{taskId}/records（已实现，本轮扩展 source/更正留痕字段，向后兼容）。
 * 数据范围由后端裁定（_check_course_scope）：任课教师仅见本人教学班任务，
 * 学院教务员/教务处管理员/学校管理员不受 COURSE 范围收敛。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const STATUS_LABEL = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '待学院审核', COLLEGE_REVIEW: '学院审核中',
  ACADEMIC_REVIEW: '待教务终审', PUBLISHED: '已发布', RETURNED: '已退回', ARCHIVED: '已归档'
}
const SOURCE_LABEL = { LEGACY: '历史数据', PUBLISH: '正常发布', CHANGE: '更正后', MANUAL: '人工维护' }
const EXCEPTION_LABEL = { NORMAL: '正常', ABSENT: '缺考', DEFERRED: '缓考', EXEMPT: '免修' }

export default {
  name: 'AaGradeRecheckView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      statusFilter: '',
      taskLoading: true, taskError: '', taskRows: [],
      taskPagination: { page: 1, pageSize: 10, total: 0 },
      taskColumns: [
        { key: 'courseName', title: '课程' },
        { key: 'termCode', title: '学期' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '120px' }
      ],
      activeTask: null,
      recordLoading: false, recordError: '', recordRows: [],
      recordColumns: [
        { key: 'recordId', title: '记录ID', width: '90px' },
        { key: 'studentNo', title: '学号' },
        { key: 'realName', title: '姓名' },
        { key: 'usualScore', title: '平时分' },
        { key: 'finalScore', title: '期末分' },
        { key: 'totalScore', title: '总评' },
        { key: 'passStatus', title: '结果' },
        { key: 'exceptionFlag', title: '异常标记' },
        { key: 'source', title: '来源' },
        { key: 'prevTotalScore', title: '更正前总评' },
        { key: 'changeReason', title: '更正原因' },
        { key: 'changeAt', title: '更正时间' }
      ]
    }
  },
  created() {
    this.loadTasks()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s },
    sourceLabel(s) { return SOURCE_LABEL[s] || s || '—' },
    exceptionLabel(s) { return EXCEPTION_LABEL[s] || s || '正常' },
    formatTime(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },
    onFilterChange() { this.taskPagination.page = 1; this.loadTasks() },
    onTaskPageChange(p) { this.taskPagination.page = p; this.loadTasks() },
    async loadTasks() {
      this.taskLoading = true
      this.taskError = ''
      const res = await academicAffairsApi.getGradeTasks({
        status: this.statusFilter || undefined,
        page: this.taskPagination.page,
        pageSize: this.taskPagination.pageSize
      })
      if (res.code === 0) {
        this.taskRows = res.data.list
        this.taskPagination.total = res.data.total
      } else {
        this.taskError = res.message
      }
      this.taskLoading = false
    },
    async loadRecords(row) {
      this.activeTask = row
      this.recordLoading = true
      this.recordError = ''
      this.recordRows = []
      const res = await academicAffairsApi.getGradeRecords(row.gradeTaskId)
      if (res.code === 0) this.recordRows = res.data.items || []
      else this.recordError = res.message
      this.recordLoading = false
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
