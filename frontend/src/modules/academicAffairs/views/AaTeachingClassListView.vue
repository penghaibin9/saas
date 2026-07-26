<template>
  <ModulePageShell
    title="教学班与名单版本"
    subtitle="统一查看教学班、主讲教师、当前正式名单和历史版本；旧教学任务字段继续保留兼容"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/teaching-tasks')">教学任务</AppButton>
      <AppButton :disabled="!filters.termId" :loading="checking" @click="runBackfill(true)">存量对账</AppButton>
      <AppButton variant="primary" :disabled="!filters.termId || !backfillReport" @click="confirmVisible = true">执行回填</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert
        type="info"
        title="名单版本是正式成员事实"
        description="选课未锁定时下游业务仍会阻断；选课锁定后生成新版本，旧版本仅标记为历史，不删除。"
      />

      <AppSectionCard title="查询范围">
        <div class="aa-filter-row">
          <label>学期
            <select v-model="filters.termId" class="aa-select" @change="load">
              <option value="">全部学期</option>
              <option v-for="term in terms" :key="term.termId" :value="term.termId">{{ term.termName || `${term.yearCode}-${term.termNo}` }}</option>
            </select>
          </label>
          <label>班型
            <select v-model="filters.classType" class="aa-select" @change="load">
              <option value="">全部</option><option value="ADMIN">行政班开课</option><option value="SELECTION">选课教学班</option><option value="MERGED">合班</option><option value="RETAKE">重修班</option><option value="LAYERED">分层班</option>
            </select>
          </label>
          <label>状态
            <select v-model="filters.status" class="aa-select" @change="load">
              <option value="">全部</option><option value="ACTIVE">使用中</option><option value="ARCHIVED">已归档</option>
            </select>
          </label>
          <label class="is-grow">搜索
            <input v-model.trim="filters.keyword" class="aa-input" placeholder="教学班编号、名称或课程" @keyup.enter="load" />
          </label>
          <AppButton variant="primary" :loading="loading" @click="load">查询</AppButton>
        </div>
      </AppSectionCard>

      <div v-if="rows.length" class="aa-summary-grid">
        <div><strong>{{ pagination.total }}</strong><span>教学班总数</span></div>
        <div><strong>{{ activeCount }}</strong><span>当前使用中</span></div>
        <div><strong>{{ lockedCount }}</strong><span>名单已锁定</span></div>
        <div :class="{ 'is-danger': debtCount }"><strong>{{ debtCount }}</strong><span>尚无正式版本</span></div>
      </div>

      <AppInlineAlert
        v-if="backfillReport"
        :type="backfillReport.readyCount === backfillReport.taskCount ? 'success' : 'warning'"
        title="存量对账结果"
        :description="`共 ${backfillReport.taskCount} 条教学任务，其中 ${backfillReport.readyCount} 条可形成正式名单；执行回填前请处理未就绪任务。`"
      />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无教学班投影" description="先生成教学任务，再运行存量对账；系统不会在数据库迁移中自动猜测名单" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="teachingClassId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-class="{ row }">
          <div class="mp-cell-main">{{ row.className }}</div>
          <div class="mp-cell-sub">{{ row.classCode }} · {{ classTypeLabel(row.classType) }}</div>
        </template>
        <template #cell-course="{ row }"><div class="mp-cell-main">{{ row.courseName || '—' }}</div><div class="mp-cell-sub">{{ row.courseCode || row.courseId }}</div></template>
        <template #cell-teacher="{ row }"><div class="mp-cell-main">{{ primaryTeacher(row)?.teacherName || '待分配' }}</div><div class="mp-cell-sub">{{ primaryTeacher(row)?.teacherKey || '—' }}</div></template>
        <template #cell-roster="{ row }">
          <AppStatusTag :type="row.rosterStatus === 'LOCKED' ? 'success' : 'warning'" :label="row.rosterStatus === 'LOCKED' ? `第${row.rosterVersionNo}版` : '待形成名单'" dot />
          <div class="mp-cell-sub">{{ row.expectedStudents ?? 0 }}人</div>
        </template>
        <template #cell-status="{ row }"><AppStatusTag :status="row.status" dot /></template>
        <template #cell-actions="{ row }"><button class="mp-link" @click="$router.push(`/admin/academic-affairs/teaching-classes/${row.teachingClassId}`)">查看名单与版本</button></template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      title="执行教学班与名单版本回填"
      type="warning"
      confirm-text="确认回填"
      require-reason
      reason-label="回填说明（≥5字）"
      :submitting="backfilling"
      @confirm="executeBackfill"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert, AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { teachingClassApi } from '@/modules/academicAffairs/api/teaching-class.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeachingClassListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppConfirmDialog, AppInlineAlert, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, checking: false, backfilling: false, error: '', rows: [], terms: [],
      filters: { termId: '', classType: '', status: 'ACTIVE', keyword: '' },
      pagination: { page: 1, pageSize: 30, total: 0 },
      backfillReport: null, confirmVisible: false,
      columns: [
        { key: 'class', title: '教学班' }, { key: 'course', title: '课程' },
        { key: 'teacher', title: '主讲教师', width: '160px' }, { key: 'roster', title: '当前名单', width: '145px' },
        { key: 'status', title: '状态', width: '105px' }, { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  computed: {
    activeCount() { return this.rows.filter(row => row.status === 'ACTIVE').length },
    lockedCount() { return this.rows.filter(row => row.rosterStatus === 'LOCKED').length },
    debtCount() { return this.rows.filter(row => row.rosterStatus !== 'LOCKED').length }
  },
  async created() { await this.loadTerms(); await this.load() },
  methods: {
    classTypeLabel(value) { return ({ ADMIN: '行政班', SELECTION: '选课班', MERGED: '合班', RETAKE: '重修班', LAYERED: '分层班' })[value] || value || '—' },
    primaryTeacher(row) { return (row.teachers || []).find(item => item.roleType === 'PRIMARY' && item.status === 'ACTIVE') },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async loadTerms() {
      const [termsRes, currentRes] = await Promise.all([academicAffairsApi.getTerms({ page: 1, pageSize: 50 }), academicAffairsApi.getCurrentTerm()])
      if (termsRes.code === 0) this.terms = termsRes.data.list || []
      if (currentRes.code === 0 && currentRes.data?.termId) this.filters.termId = String(currentRes.data.termId)
    },
    async load() {
      if (this.loading) return
      this.loading = true; this.error = ''
      const res = await teachingClassApi.list({
        termId: this.filters.termId || undefined, classType: this.filters.classType || undefined,
        status: this.filters.status || undefined, keyword: this.filters.keyword || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list || []; this.pagination.total = res.data.total || 0 }
      else { this.rows = []; this.pagination.total = 0; this.error = res.message || '加载教学班失败' }
      this.loading = false
    },
    async runBackfill(dryRun) {
      if (!this.filters.termId || this.checking) return
      this.checking = true
      const res = await teachingClassApi.backfill(this.filters.termId, dryRun)
      this.checking = false
      if (res.code === 0) { this.backfillReport = res.data; toast.success('存量对账完成') }
      else toast.error(res.message || '存量对账失败')
    },
    async executeBackfill({ reason }) {
      if (this.backfilling) return
      if (!reason || reason.trim().length < 5) { toast.error('请填写不少于5字的回填说明'); return }
      this.backfilling = true
      const res = await teachingClassApi.backfill(this.filters.termId, false)
      this.backfilling = false
      if (res.code === 0) { this.confirmVisible = false; this.backfillReport = res.data; toast.success('教学班与名单版本回填完成'); await this.load() }
      else toast.error(res.message || '回填失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter-row { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; }
.aa-filter-row label { display: flex; min-width: 150px; flex-direction: column; gap: 6px; color: var(--text-700, #4e5969); font-size: 13px; }
.aa-filter-row label.is-grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); }
.aa-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-summary-grid > div { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary-grid strong, .aa-summary-grid span { display: block; }
.aa-summary-grid strong { font-size: 23px; }.aa-summary-grid span { margin-top: 4px; color: var(--text-500, #64748b); font-size: 12px; }
.aa-summary-grid .is-danger { border-color: var(--danger-200, #fecaca); }
@media (max-width: 850px) { .aa-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
