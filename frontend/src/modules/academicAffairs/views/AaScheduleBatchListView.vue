<template>
  <ModulePageShell
    class="aa-schedule-workspace"
    :title="onlyArchived ? '排课归档' : '课表批次'"
    :subtitle="onlyArchived ? '查看已归档的课表和发布记录。' : '选择批次继续排课或查看已发布课表。'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="onlyArchived" @click="$router.push('/admin/academic-affairs/schedule')">返回课表批次</AppButton>
      <AppButton v-if="$route.query.returnToken" @click="academicFlow?.back($route.query.returnToken, '/admin/academic-affairs/teaching-tasks')">返回教学任务</AppButton>
      <AppButton v-else-if="taskReturnTo" @click="$router.push(taskReturnTo)">返回教学任务</AppButton>
      <AppButton v-if="!onlyArchived" variant="primary" @click="showCreate = !showCreate">＋ 创建排课批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-pagebar" aria-label="课表批次查询">
        <div class="aa-schedule-term"><AppTermEntityPicker v-model="termId" clearable placeholder="全部学期" aria-label="学期" @change="searchBatches" /></div>
        <AppButton variant="ghost" :disabled="loading" @click="load">刷新</AppButton>
        <ul v-if="!onlyArchived && !loading && !error" class="aa-stat-strip" aria-label="课表批次状态概览">
          <li><span>共</span><b>{{ pagination.total }}</b></li>
          <li><span>编制中</span><b>{{ statusCount('DRAFT') }}</b></li>
          <li class="is-warning"><span>已预发布</span><b>{{ statusCount('PRE_PUBLISHED') }}</b></li>
          <li class="is-success"><span>已发布/归档</span><b>{{ statusCount('PUBLISHED') + statusCount('ARCHIVED') }}</b></li>
        </ul>
        <span v-if="onlyArchived" class="aa-schedule-note">归档后只读，更正须另建版本。</span>
      </div>

      <AppSectionCard compact v-if="showCreate" title="新建课表批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item">
            学期
            <AppTermEntityPicker v-model="draft.termId" placeholder="选择学期" />
          </label>
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称<input v-model.trim="draft.batchName" class="aa-input" placeholder="选填" maxlength="50" />
          </label>
          <label class="aa-cal-form__item">排课范围
            <select v-model="draft.scopeType" class="aa-input" aria-label="排课范围" :disabled="creating">
              <option value="COLLEGE">指定学院</option>
              <option value="SCHOOL">全校</option>
            </select>
          </label>
          <label v-if="draft.scopeType === 'COLLEGE'" class="aa-cal-form__item">学院
            <AppCollegePicker v-model="draft.collegeId" placeholder="选择排课学院" :disabled="creating" />
          </label>
          <AppButton variant="primary" :disabled="!draft.termId || (draft.scopeType === 'COLLEGE' && !draft.collegeId)" :loading="creating" @click="createBatch">创建</AppButton>
        </div>
        <p class="mp-note">须排齐所选范围的教学任务；新建批次不复制原有课程安排。</p>
        <p class="mp-note">调整已发布课表时，从“核对进度与补排”创建保留原安排的纠错草稿。</p>
      </AppSectionCard>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="onlyArchived ? '暂无已归档批次' : '还没有课表批次'" :description="onlyArchived ? '学期结束后可将已发布课表归档。' : '新建一个课表批次开始排课'" />
      <AppSectionCard v-else-if="rows.length" compact :title="onlyArchived ? '归档批次' : '批次列表'">
      <DataTable :columns="columns" :rows="rows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-batchName="{ row }">
          <div class="mp-cell-main">{{ row.batchName }}</div>
        </template>
        <template #cell-termId="{ row }">{{ row.termLabel || '学期待核对' }}</template>
        <template #cell-scope="{ row }">
          {{ Object.prototype.hasOwnProperty.call(row, 'collegeId') ? (row.collegeId ? row.collegeName || '指定学院' : '全校范围') : '范围待核对' }}
        </template>
        <template #cell-version="{ row }">{{ row.publishedVersion != null ? `当前正式第${row.publishedVersion}版` : ['DRAFT', 'PRE_PUBLISHED'].includes(row.status) ? '尚未正式发布' : ['SUPERSEDED', 'ARCHIVED', 'VOIDED'].includes(row.status) ? '历史版本，查看记录' : '生效版本待核对' }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="scheduleBatchColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <div class="aa-actions">
            <button class="mp-link" @click="openBatch(row)">{{ ['DRAFT', 'PRE_PUBLISHED'].includes(row.status) ? '继续排课' : row.status === 'ARCHIVED' ? '查看归档课表' : row.status === 'PUBLISHED' ? '查看已发布课表' : '查看课表记录' }}</button>
            <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openWorkbench(row)">核对进度与补排</button>
            <button v-if="['DRAFT', 'PRE_PUBLISHED'].includes(row.status)" class="mp-link" @click="openBatch(row, 'views')">查看班级、教师与教室课表</button>
            <button v-if="row.status === 'DRAFT'" class="mp-link" :disabled="!!writingId" @click="act(row, 'pre')">预发布</button>
            <button v-if="row.status === 'PRE_PUBLISHED'" class="mp-link" :disabled="!!writingId" @click="act(row, 'pub')">发布</button>
            <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openChangeLedger(row)">调停课台账</button>
            <button v-if="row.status === 'PUBLISHED'" class="mp-link aa-danger" @click="openVoid(row)">作废重发（重大纠错）</button>
            <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openArchive(row)">归档</button>
          </div>
        </template>
      </DataTable>
      </AppSectionCard>
      <template v-if="!onlyArchived">
        <p class="mp-note">发布后不可直接修改，日常调课、停课、补课走“调停课”审批。</p>
        <p class="mp-note">整批重大错误才作废重发；学期结束后归档，归档后仅供查看。</p>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="voidDlg.visible"
      title="作废重发课表批次"
      type="danger"
      confirm-text="确认作废"
      :require-reason="true"
      reason-label="作废原因"
      :submitting="voidDlg.submitting"
      @confirm="doVoid"
    />

    <AppConfirmDialog
      v-model:visible="archiveDlg.visible"
      title="归档课表批次"
      type="warning"
      confirm-text="确认归档"
      message="请确认学期已结束；归档不可撤销，归档后课表仅供查看，无法调整。"
      :submitting="archiveDlg.submitting"
      @confirm="doArchive"
    />
  </ModulePageShell>
</template>

<script>
/** 课表批次列表（/admin/academic-affairs/schedule）：GET/POST /academic-affairs/schedule-batches + 发布/作废。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppTermEntityPicker, AppCollegePicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { SCHEDULE_BATCH_STATUS, scheduleBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaScheduleBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppTermEntityPicker, AppCollegePicker },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loading: true, error: '', rows: [], termId: '', revision: 0, disposed: false, writingId: '',
      showCreate: false, creating: false, draft: { termId: '', batchName: '', scopeType: 'COLLEGE', collegeId: '' },
      voidDlg: { visible: false, submitting: false, batchId: '' },
      archiveDlg: { visible: false, submitting: false, batchId: '' },
      onlyArchived: false,
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'termId', title: '学期' },
        { key: 'scope', title: '适用范围' },
        { key: 'version', title: '版本' },
        { key: 'status', title: '当前状态' },
        { key: 'actions', title: '操作', width: '360px' }
      ]
    }
  },
  computed: {
    taskReturnTo() { const target = this.$route.query.returnTo; return typeof target === 'string' && /^\/admin\/academic-affairs\/teaching-tasks(?:[/?]|$)/.test(target) ? target : '' }
  },
  watch: {
    '$route.fullPath'() { this.restoreQuery(); this.load() },
    ctx() { this.revision++; this.rows = []; this.showCreate = false; this.voidDlg.visible = false; this.archiveDlg.visible = false; this.load() }
  },
  created() {
    // ?panel=archive 深链接（排课归档三级菜单入口）：直接打开「只看已归档」视图
    this.restoreQuery()
    this.load()
  },
  beforeUnmount() { this.disposed = true; this.revision++ },
  methods: {
    scheduleBatchColor,
    statusLabel(s) { return SCHEDULE_BATCH_STATUS[s] || (s ? '状态待确认' : '') },
    statusCount(status) { return this.rows.filter((row) => row.status === status).length },
    restoreQuery() {
      const q = this.$route?.query || {}
      this.onlyArchived = q.panel === 'archive'; this.termId = typeof q.termId === 'string' ? q.termId : ''
      const page = Number(q.page); this.pagination.page = Number.isInteger(page) && page > 0 && page <= 1000000 ? page : 1
      this.draft.termId = this.termId
    },
    searchBatches() { return this.onPageChange(1) },
    async onPageChange(p) {
      const before = this.$route.fullPath
      await this.$router.push({ path: this.$route.path, query: { ...this.$route.query, termId: this.termId || undefined, page: String(p) } })
      if (before === this.$route.fullPath) return this.load()
    },
    openBatch(row, view) {
      const returnToken = this.academicFlow?.captureReturn?.()
      const page = ['DRAFT', 'PRE_PUBLISHED'].includes(row.status) && view !== 'views' ? 'edit' : 'views'
      this.$router.push({ path: `/admin/academic-affairs/schedule/${row.batchId}/${page}`, query: { ...(returnToken ? { returnToken } : {}) } })
    },
    openChangeLedger(row) { this.$router.push({ path: '/admin/academic-affairs/schedule-change', query: { termId: row.termId || '' } }) },
    openWorkbench(row) { this.$router.push({ path: '/admin/academic-affairs/scheduling', query: { batchId: String(row.batchId), tab: 'workbench' } }) },
    async createBatch() {
      if (this.creating || !this.draft.termId || !['COLLEGE', 'SCHOOL'].includes(this.draft.scopeType) || (this.draft.scopeType === 'COLLEGE' && !this.draft.collegeId)) return
      this.creating = true
      const context = this.ctx
      try {
        const res = await academicAffairsApi.createScheduleBatch({ termId: this.draft.termId, batchName: this.draft.batchName || undefined, collegeId: this.draft.scopeType === 'COLLEGE' ? this.draft.collegeId : undefined })
        if (this.disposed || context !== this.ctx) return
        if (res.code === 0) { toast.success('课表批次已创建'); this.showCreate = false; this.draft = { termId: this.termId, batchName: '', scopeType: 'COLLEGE', collegeId: '' }; await this.load() }
        else { toast.error(res.message || '创建失败，请核对批次列表') }
      } catch { if (!this.disposed && context === this.ctx) toast.error('创建结果待核对，请先刷新批次列表') }
      finally { this.creating = false }
    },
    async act(row, kind) {
      if (this.writingId) return
      const context = this.ctx, id = String(row.batchId)
      const current = () => !this.disposed && context === this.ctx
      this.writingId = id
      try {
        const fn = kind === 'pre' ? academicAffairsApi.prePublishSchedule : academicAffairsApi.publishSchedule
        const res = await fn(id)
        if (!current()) return
        if (res.code !== 0) { toast.error(res.message || '操作失败，请刷新批次核对'); return }
        const fresh = await academicAffairsApi.getScheduleBatch(id)
        if (!current()) return
        const expected = kind === 'pre' ? 'PRE_PUBLISHED' : 'PUBLISHED'
        if (fresh.code !== 0 || String(fresh.data?.batchId) !== id || fresh.data?.status !== expected) {
          toast.error('操作结果尚未核实，请刷新批次确认'); return
        }
        toast.success(kind === 'pre' ? '当前批次已预发布，可继续发布' : '当前课表已发布，通知情况请查看发布记录')
        await this.load()
      } catch (error) { if (current()) toast.error(error?.message || '操作结果待核实，请刷新后核对') }
      finally { this.writingId = '' }
    },
    openVoid(row) { this.voidDlg = { visible: true, submitting: false, batchId: row.batchId } },
    async doVoid(payload) {
      const reason = (payload && payload.reason) || ''
      this.voidDlg.submitting = true
      const res = await academicAffairsApi.voidReissueSchedule(this.voidDlg.batchId, reason)
      this.voidDlg.submitting = false
      if (res.code === 0) { this.voidDlg.visible = false; toast.success('已作废'); this.load() }
      else { toast.error(res.message || '作废失败') }
    },
    openArchive(row) { this.archiveDlg = { visible: true, submitting: false, batchId: row.batchId } },
    async doArchive() {
      this.archiveDlg.submitting = true
      const res = await academicAffairsApi.archiveSchedule(this.archiveDlg.batchId)
      this.archiveDlg.submitting = false
      if (res.code === 0) { this.archiveDlg.visible = false; toast.success('已归档'); this.load() }
      else { toast.error(res.message || '归档失败') }
    },
    async load() {
      const revision = ++this.revision, context = this.ctx
      const current = () => !this.disposed && revision === this.revision && context === this.ctx
      this.loading = true
      this.error = ''; this.rows = []; this.pagination.total = 0
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (this.termId) params.termId = this.termId
      if (this.onlyArchived) params.status = 'ARCHIVED'
      try {
        const res = await academicAffairsApi.getScheduleBatches(params)
        if (!current()) return
        if (res.code === 0) { this.rows = res.data?.list || []; this.pagination.total = res.data?.total || 0 }
        else { this.error = res.message || '课表批次读取失败'; this.rows = [] }
      } catch (error) {
        if (!current()) return
        this.error = error?.message || '网络连接中断，未能读取课表批次'
        this.rows = []
      } finally { if (current()) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/schedule-workspace.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-danger { color: var(--danger-600, #f53f3f); }
.aa-actions { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; }
.aa-actions button { white-space: nowrap; }
.aa-schedule-workspace :deep(.dt__table) { min-width: 1040px; }
.aa-schedule-workspace :deep(.dt__th:first-child), .aa-schedule-workspace :deep(.dt__td:first-child) { min-width: 220px; }
.aa-archive-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-right: 12px; }
.aa-batch-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.aa-batch-metrics article { display: grid; gap: 7px; padding: 17px 18px; border: 1px solid var(--border-200, #dbe3ed); border-radius: 12px; background: var(--bg-white, #fff); }
.aa-batch-metrics span { color: var(--text-500, #68788c); font-size: 12px; }
.aa-batch-metrics strong { color: var(--text-900, #193252); font-size: 26px; line-height: 1; }
.aa-batch-metrics small { color: var(--text-400, #8794aa); font-size: 11px; }
@media (max-width: 900px) { .aa-batch-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

.aa-schedule-term { width: 220px; }
.aa-schedule-note { color: var(--t3, #65778b); font-size: 12px; }
</style>
<style>
@import '../styles/page-compact.css';
</style>
