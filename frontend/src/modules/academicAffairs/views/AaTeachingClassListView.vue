<template>
  <ModulePageShell
    title="教学班与名单版本"
    subtitle="统一查看教学班、主讲教师、当前正式名单和历史版本；旧教学任务字段继续保留兼容"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/teaching-tasks')">教学任务</AppButton>
      <AppButton v-if="canManage" :disabled="!filters.termId" :loading="checking" @click="runBackfill">存量对账</AppButton>
      <AppButton v-if="canManage" variant="primary" :disabled="!canExecuteBackfill" @click="confirmVisible = true">执行回填</AppButton>
    </template>

    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AppInlineAlert
        type="info"
        title="名单版本是正式成员事实"
        description="选课未锁定时下游业务仍会阻断；选课锁定后生成新版本，旧版本仅标记为历史，不删除。"
      />

      <AppSectionCard title="查询范围">
        <div class="aa-filter-row">
          <label>学期
            <select v-model="filters.termId" class="aa-select" @change="onTermChange">
              <option value="" disabled>请选择学期</option>
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
          <AppButton variant="primary" :disabled="!initialized || !filters.termId" :loading="loading" @click="load">查询</AppButton>
        </div>
      </AppSectionCard>

      <div v-if="rows.length" class="aa-summary-grid">
        <div><strong>{{ pagination.total }}</strong><span>教学班总数</span></div>
        <div><strong>{{ activeCount }}</strong><span>当前页使用中</span></div>
        <div><strong>{{ lockedCount }}</strong><span>当前页名单已锁定</span></div>
        <div :class="{ 'is-danger': debtCount }"><strong>{{ debtCount }}</strong><span>当前页尚无正式版本</span></div>
      </div>

      <AppInlineAlert
        v-if="backfillReport"
        :type="canExecuteBackfill ? 'success' : 'warning'"
        title="存量对账结果"
        :description="backfillDescription"
      />

      <ErrorState v-if="error" :description="error" @retry="retryLoad" />
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
          <div class="mp-cell-sub">预计人数 {{ row.expectedStudents ?? '未提供' }}</div>
        </template>
        <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ACTIVE' ? 'success' : 'info'" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }"><button class="mp-link" @click="openDetail(row)">查看名单与版本</button></template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      title="执行教学班与名单版本回填"
      type="warning"
      confirm-text="确认回填"
      require-reason
      reason-label="回填原因（≥5字）"
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
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult, isMissingResult } from '../components/parallel-a/resultState'

export default {
  name: 'AaTeachingClassListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppConfirmDialog, AppInlineAlert, AppSectionCard, AppStatusTag, AaOperationReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, initialized: false, initRevision: 0, checking: false, backfilling: false, error: '', rows: [], terms: [],
      filters: { termId: '', classType: '', status: 'ACTIVE', keyword: '' },
      pagination: { page: 1, pageSize: 30, total: 0 },
      backfillReport: null, confirmVisible: false,
      revision: 0, checkRevision: 0, checkedTermId: '', receipt: null,
      columns: [
        { key: 'class', title: '教学班' }, { key: 'course', title: '课程' },
        { key: 'teacher', title: '主讲教师', width: '160px' }, { key: 'roster', title: '当前名单', width: '145px' },
        { key: 'status', title: '状态', width: '105px' }, { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.manage') },
    activeCount() { return this.rows.filter(row => row.status === 'ACTIVE').length },
    lockedCount() { return this.rows.filter(row => row.rosterStatus === 'LOCKED').length },
    debtCount() { return this.rows.filter(row => row.rosterStatus !== 'LOCKED').length },
    canExecuteBackfill() {
      const total = Number(this.backfillReport?.taskCount || 0)
      return Boolean(this.canManage && this.checkedTermId === this.filters.termId && this.filters.termId && total > 0 && Number(this.backfillReport?.readyCount || 0) === total)
    },
    backfillDescription() {
      const total = Number(this.backfillReport?.taskCount || 0)
      const ready = Number(this.backfillReport?.readyCount || 0)
      const blocked = Number(this.backfillReport?.blockedCount ?? Math.max(total - ready, 0))
      if (!total) return '当前范围没有可回填的教学任务，不会写入空批次。'
      if (blocked) return `共 ${total} 条教学任务，${ready} 条名单就绪、${blocked} 条阻断；必须全部处理完才能正式回填。`
      return `共 ${total} 条教学任务，名单全部就绪；正式回填将一次性生成教学班和名单版本并写入审计。`
    }
  },
  created() { this.initialize() },
  watch: { ctx() { this.revision++; this.checkRevision++; this.terms = []; this.rows = []; this.pagination.total = 0; this.receipt = null; this.backfillReport = null; this.checkedTermId = ''; this.confirmVisible = false; this.checking = false; this.backfilling = false; this.filters = { termId: '', classType: '', status: 'ACTIVE', keyword: '' }; this.initialize() } },
  beforeUnmount() { this.revision++; this.checkRevision++; this.initRevision++; this.disposed = true },
  methods: {
    async initialize() {
      const revision = ++this.initRevision, context = this.ctx
      const current = () => !this.disposed && revision === this.initRevision && context === this.ctx
      this.loading = true; this.initialized = false; this.error = ''
      try {
        await this.loadTerms(current)
        if (!current()) return
        this.initialized = true
        await this.load()
      } catch (error) { if (current()) this.handleFailure(error, '学期读取失败，请重试；尚未查询教学班。') }
      finally { if (current()) this.loading = false }
    },
    retryLoad() { return this.initialized ? this.load() : this.initialize() },
    classTypeLabel(value) { return ({ ADMIN: '行政班', SELECTION: '选课班', MERGED: '合班', RETAKE: '重修班', LAYERED: '分层班' })[value] || (value ? '待确认' : '—') },
    statusLabel(value) { return ({ ACTIVE: '使用中', ARCHIVED: '已归档' })[value] || (value ? '待确认' : '—') },
    primaryTeacher(row) { return (row.teachers || []).find(item => item.roleType === 'PRIMARY' && item.status === 'ACTIVE') },
    openDetail(row) { this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { view: 'classes', teachingClassId: row.teachingClassId, termId: this.filters.termId || undefined, returnTo: this.$route.fullPath } }) },
    onPageChange(page) { this.pagination.page = page; this.load() },
    onTermChange() { this.checkRevision++; this.checking = false; this.checkedTermId = ''; this.backfillReport = null; this.confirmVisible = false; this.pagination.page = 1; this.load() },
    async loadTerms(current = () => !this.disposed) {
      const [termsRes, currentRes] = await Promise.all([academicAffairsApi.getTerms({ page: 1, pageSize: 50 }), academicAffairsApi.getCurrentTerm()])
      if (!current()) return
      if (termsRes.code !== 0) throw termsRes
      if (currentRes.code !== 0 && !isMissingResult(currentRes)) throw currentRes
      if (!Array.isArray(termsRes.data?.list)) throw new Error('学期列表未完整返回，请重试。')
      this.terms = termsRes.data.list
      if (this.$route.query.termId) this.filters.termId = String(this.$route.query.termId)
      else if (currentRes.code === 0 && currentRes.data?.termId) this.filters.termId = String(currentRes.data.termId)
    },
    async load() {
      if (this.disposed) return
      if (!this.initialized || !this.filters.termId || !this.terms.some(term => String(term.termId) === String(this.filters.termId))) {
        this.revision++; this.rows = []; this.pagination.total = 0; this.loading = false
        this.error ||= '请先完成学期读取并选择有效学期，尚未查询教学班。'
        return
      }
      const revision = ++this.revision, context = this.ctx
      this.loading = true; this.error = ''
      this.rows = []; this.pagination.total = 0
      try {
      const res = await teachingClassApi.list({
        termId: this.filters.termId || undefined, classType: this.filters.classType || undefined,
        status: this.filters.status || undefined, keyword: this.filters.keyword || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (revision !== this.revision || context !== this.ctx) return
      if (res.code === 0) { this.rows = res.data.list || []; this.pagination.total = res.data.total || 0 }
      else this.handleFailure(res, '加载教学班失败')
      } catch (error) { if (revision === this.revision && context === this.ctx) this.handleFailure(error, '网络连接失败，请重试。') }
      finally { if (revision === this.revision && context === this.ctx) this.loading = false }
    },
    async runBackfill() {
      if (!this.canManage || !this.filters.termId || this.checking || this.backfilling) return
      const termId = this.filters.termId, revision = ++this.checkRevision
      this.backfillReport = null; this.checkedTermId = ''
      this.checking = true
      try {
        const res = await teachingClassApi.backfill(termId, true)
        if (revision !== this.checkRevision || termId !== this.filters.termId) return
        if (res.code === 0) { this.backfillReport = res.data; this.checkedTermId = termId }
        else this.handleFailure(res, '存量对账失败')
      } catch (error) { if (revision === this.checkRevision) this.handleFailure(error, '存量对账连接失败') }
      finally { if (revision === this.checkRevision) this.checking = false }
    },
    async executeBackfill({ reason }) {
      if (this.backfilling || !this.canExecuteBackfill) return
      if (!reason || reason.trim().length < 5) { toast.error('请填写不少于5字的回填原因'); return }
      this.backfilling = true
      const termId = this.filters.termId
      try {
      const check = await teachingClassApi.backfill(termId, true)
      if (this.disposed || termId !== this.filters.termId) return
      if (check.code !== 0) { this.handleFailure(check, '回填前核对失败，尚未提交。'); return }
      this.backfillReport = check.data; this.checkedTermId = termId
      if (!this.canExecuteBackfill) { this.error = '当前对账事实已变化，请核对后重新提交。'; return }
      const res = await teachingClassApi.backfill(termId, false, reason.trim())
      if (this.disposed || termId !== this.filters.termId) return
      if (res.code === 0) {
        this.confirmVisible = false
        this.backfillReport = res.data
        await this.load()
        if (!this.disposed && termId === this.filters.termId && !this.error) this.receipt = { object: `学期 #${termId}`, status: '回填请求已处理，列表已重新读取', next: '逐班打开正式名单及版本核对；当前页不代表全学期验收通过。' }
      } else {
        this.handleFailure(res, '回填失败')
      }
      } catch (error) { if (!this.disposed) this.handleFailure(error, '连接中断，请读取正式名单确认，勿重复回填。') }
      finally { this.backfilling = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback; this.backfillReport = null; this.checkedTermId = ''
      if (isDeniedResult(result)) { this.revision++; this.loading = false; this.rows = []; this.confirmVisible = false; this.receipt = null }
      else if (isConflictResult(result)) this.receipt = { object: `学期 #${this.filters.termId}`, status: '事实已变化，保留输入', pending: true, next: '重新执行存量对账，再核对回填范围。' }
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
