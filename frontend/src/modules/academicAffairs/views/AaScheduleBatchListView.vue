<template>
  <ModulePageShell
    title="课表管理"
    subtitle="按学期建立课表批次 → 手工/导入排课（三重冲突检测）→ 预发布 → 发布通知师生"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <label class="aa-archive-toggle"><input type="checkbox" v-model="onlyArchived" @change="load" /> 只看已归档</label>
      <button class="mp-btn mp-btn--primary" @click="showCreate = !showCreate">＋ 新建课表批次</button>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="showCreate" title="新建课表批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item">
            学期
            <select v-model="draft.termId" class="aa-select">
              <option value="">选择学期…</option>
              <option v-for="t in terms" :key="t.termId" :value="t.termId">{{ t.yearCode }} 第 {{ t.termNo }} 学期</option>
            </select>
          </label>
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称<input v-model.trim="draft.batchName" class="aa-input" placeholder="选填" maxlength="50" />
          </label>
          <button class="mp-btn mp-btn--primary" :disabled="creating || !draft.termId" @click="createBatch">{{ creating ? '创建中…' : '创建' }}</button>
        </div>
      </AppSectionCard>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有课表批次" :description="onlyArchived ? '暂无已归档批次' : '新建一个课表批次开始排课'" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-status="{ row }">
          <AppStatusTag :type="scheduleBatchColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/schedule/${row.batchId}/edit`)">排课</button>
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/schedule/${row.batchId}/views`)">三视图</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link" @click="act(row, 'pre')">预发布</button>
          <button v-if="row.status === 'PRE_PUBLISHED'" class="mp-link" @click="act(row, 'pub')">发布</button>
          <button v-if="row.status === 'PUBLISHED'" class="mp-link aa-danger" @click="openVoid(row)">作废重发</button>
          <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openArchive(row)">归档</button>
        </template>
      </DataTable>
      <p class="mp-note">发布后课表项不可直改；如需调整走「作废重发」（原因必填，留审计），再新建批次重排；学期结束请走「归档」，与「作废重发」语义不同，归档后数据只读供教务归档统一消费。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="voidDlg.visible"
      title="作废重发课表批次"
      type="danger"
      confirm-text="确认作废"
      :require-reason="true"
      phrase-scene-key="aa.void"
      reason-label="作废原因"
      :submitting="voidDlg.submitting"
      @confirm="doVoid"
    />

    <AppConfirmDialog
      v-model:visible="archiveDlg.visible"
      title="归档课表批次"
      type="warning"
      confirm-text="确认归档"
      message="归档为不可逆操作：归档后课表只读，无法再调整。确认该批次已到学期结束、可正式归档？"
      :submitting="archiveDlg.submitting"
      @confirm="doArchive"
    />
  </ModulePageShell>
</template>

<script>
/** 课表批次列表（/admin/academic-affairs/schedule）：GET/POST /academic-affairs/schedule-batches + 发布/作废。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { SCHEDULE_BATCH_STATUS, scheduleBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaScheduleBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], terms: [],
      showCreate: false, creating: false, draft: { termId: '', batchName: '' },
      voidDlg: { visible: false, submitting: false, batchId: '' },
      archiveDlg: { visible: false, submitting: false, batchId: '' },
      onlyArchived: false,
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '260px' }
      ]
    }
  },
  created() {
    // ?panel=archive 深链接（排课归档三级菜单入口）：直接打开「只看已归档」视图
    if (this.$route && this.$route.query && this.$route.query.panel === 'archive') this.onlyArchived = true
    this.load()
    this.loadTerms()
  },
  methods: {
    scheduleBatchColor,
    statusLabel(s) { return SCHEDULE_BATCH_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
    },
    async createBatch() {
      if (this.creating || !this.draft.termId) return
      this.creating = true
      const res = await academicAffairsApi.createScheduleBatch({ termId: this.draft.termId, batchName: this.draft.batchName || undefined })
      this.creating = false
      if (res.code === 0) { toast.success('课表批次已创建'); this.showCreate = false; this.draft = { termId: '', batchName: '' }; this.load() }
      else { toast.error(res.message || '创建失败') }
    },
    async act(row, kind) {
      const fn = kind === 'pre' ? academicAffairsApi.prePublishSchedule : academicAffairsApi.publishSchedule
      const res = await fn(row.batchId)
      if (res.code === 0) { toast.success(kind === 'pre' ? '已预发布' : '已发布，已通知师生'); this.load() }
      else { toast.error(res.message || '操作失败') }
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
      this.loading = true
      this.error = ''
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (this.onlyArchived) params.status = 'ARCHIVED'
      const res = await academicAffairsApi.getScheduleBatches(params)
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-danger { color: var(--danger-600, #f53f3f); }
.aa-archive-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-right: 12px; }
</style>
