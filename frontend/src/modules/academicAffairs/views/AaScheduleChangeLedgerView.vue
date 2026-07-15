<template>
  <ModulePageShell
    title="调停课台账"
    :subtitle="'共 ' + total + ' 条 · 调课/停课/补课全流程留痕（原课位改写保留历史）'"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions>
      <div class="sc-actions">
        <button class="mp-btn mp-btn--primary" @click="goApply">＋ 发起调停课</button>
        <button class="mp-btn" @click="goApproval">审批工作台</button>
      </div>
    </template>

    <div class="mp-stack">
      <div class="sc-stats" v-if="stat">
        <div class="sc-stat"><b>{{ stat.total }}</b><span>总单量</span></div>
        <div class="sc-stat"><b>{{ stat.byType.ADJUST || 0 }}</b><span>调课</span></div>
        <div class="sc-stat"><b>{{ stat.byType.STOP || 0 }}</b><span>停课</span></div>
        <div class="sc-stat"><b>{{ stat.byType.MAKEUP || 0 }}</b><span>补课</span></div>
        <div class="sc-stat"><b>{{ stat.byStatus.APPLIED || 0 }}</b><span>已生效</span></div>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无调停课单" description="点右上「＋ 发起调停课」创建" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.className || '—' }} · {{ row.teacherName || '—' }}</div>
        </template>
        <template #cell-type="{ row }"><StatusTag :type="typeTone(row.changeType)" :label="row.changeTypeLabel" dot /></template>
        <template #cell-move="{ row }">
          <span class="sc-slot">周{{ row.origin.weekday }}·{{ row.origin.slotNo }}节 {{ row.origin.classroom }}</span>
          <template v-if="row.changeType !== 'STOP'">
            <span class="sc-arrow">→</span>
            <span class="sc-slot sc-slot--to">周{{ row.target.weekday }}·{{ row.target.slotNo }}节 {{ row.target.classroom }}</span>
          </template>
          <span v-else class="sc-stop">停课</span>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">详情</button>
          <button v-if="row.status === 'APPLIED'" class="mp-link" style="margin-left: var(--space-2)" @click="goNotice(row)">通知单</button>
          <button v-if="cancellable(row)" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askCancel(row)">撤销</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      reason-label="撤销原因" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 调停课台账（/admin/academic-affairs/schedule-change）：范围过滤 + 统计 + 撤销 + 通知单入口。生产级只走真实后端。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { scheduleChangeApi, CHANGE_TYPES, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'

const EMPTY = () => ({ changeType: '', status: '', termId: '' })

export default {
  name: 'AaScheduleChangeLedgerView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY(), stat: null,
      confirm: { visible: false, title: '', message: '', type: 'danger', confirmText: '确认', requireReason: true, row: null },
      columns: [
        { key: 'course', title: '课程 / 班级·教师' },
        { key: 'type', title: '类型' },
        { key: 'move', title: '原课位 → 目标' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: CHANGE_TYPES.map((t) => ({ value: t.value, label: t.label })) },
        { key: 'status', label: '状态', type: 'select', options: CHANGE_STATUS.map((s) => ({ value: s.value, label: s.label })) },
        { key: 'termId', label: '学期ID', type: 'text', placeholder: '学期主键' }
      ]
    }
  },
  created() { this.load(); this.loadStats() },
  methods: {
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || s },
    statusTone(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    cancellable(row) { return ['SUBMITTED', 'COLLEGE_REVIEW'].includes(row.status) },
    async load() {
      this.loading = true; this.error = ''
      const res = await scheduleChangeApi.list({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    async loadStats() {
      const res = await scheduleChangeApi.stats({ termId: this.filters.termId })
      if (res.code === 0) this.stat = res.data
    },
    search() { this.page = 1; this.load(); this.loadStats() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load(); this.loadStats() },
    turnPage(p) { this.page = p; this.load() },
    goApply() { this.$router.push('/admin/academic-affairs/schedule-change/apply') },
    goApproval() { this.$router.push('/admin/academic-affairs/schedule-change/approval') },
    // 详情/通知单共用同一打印页（D7 独立路由）；此前缺 /print/ 前缀导致 404，与已注册路由
    // （academic-affairs.routes.js 的 printScheduleChangeNoticeRoute）对齐修正。
    goDetail(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) },
    goNotice(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) },
    askCancel(row) {
      this.confirm = { visible: true, title: '撤销调停课', message: `确认撤销「${row.courseName || ''}」的${row.changeTypeLabel}申请？`, type: 'danger', confirmText: '确认撤销', requireReason: true, row }
    },
    async onConfirm({ reason } = {}) {
      this.submitting = true
      try {
        const res = await scheduleChangeApi.cancel(this.confirm.row.changeId, reason || '')
        if (res.code === 0) { toast.success('已撤销'); this.confirm.visible = false; this.load(); this.loadStats() } else toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-actions { display: flex; gap: var(--space-2); }
.sc-stats { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.sc-stat { display: flex; flex-direction: column; align-items: center; min-width: 84px; padding: 10px 14px; border: 1px solid var(--line, #e2e8f0); border-radius: 10px; }
.sc-stat b { font-size: 20px; color: var(--pri, #2563eb); }
.sc-stat span { font-size: 12px; color: var(--t3, #64748b); }
.sc-slot { font-size: 12px; color: var(--t2, #475569); }
.sc-slot--to { color: var(--pri, #2563eb); font-weight: 600; }
.sc-arrow { margin: 0 6px; color: var(--t3, #94a3b8); }
.sc-stop { color: var(--warning, #d97706); font-weight: 600; font-size: 12px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-link--danger { color: var(--danger, #dc2626); }
</style>
