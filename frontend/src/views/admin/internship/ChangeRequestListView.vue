<template>
  <ModulePageShell
    title="实习变更审核"
    subtitle="换岗 · 换实习单位 · 自主实习变更"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无变更申请" description="学生可在小程序发起换岗/换单位申请" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-change="{ row }">
          <div class="mp-cell-main">{{ row.changeTypeLabel }}</div>
          <div class="mp-cell-sub">{{ row.currentEnterprise }} / {{ row.currentPosition }}</div>
        </template>
        <template #cell-target="{ row }">
          <div class="mp-cell-main">{{ row.targetEnterpriseName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.targetPositionName || '—' }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" @click="openReview(row, 'APPROVE')">通过</button>
            <button class="mp-link mp-link--danger" @click="openReview(row, 'REJECT')">驳回</button>
          </template>
          <button v-else class="mp-link" @click="openDetail(row)">查看</button>
        </template>
      </DataTable>
    </div>

    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">变更申请详情</div>
        <div class="modal__body">
          <AppDescriptionList v-if="detailDlg.data" :items="detailItems" :columns="1" />
          <AppAuditTrail v-if="detailDlg.data" :records="auditRecords" compact empty-text="暂无留痕" />
        </div>
        <div class="modal__foot"><AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审核意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppDescriptionList, AppAuditTrail } from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ChangeRequestListView',
  components: { ModulePageShell, DataTable, AppStatusTag, AppConfirmDialog, AppDescriptionList, AppAuditTrail,
    AppButton, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [],
      filters: { status: 'PENDING' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: 'PENDING', label: '待审核' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已驳回' },
        { value: '', label: '全部' }
      ],
      columns: [
        { key: 'student', title: '学生' },
        { key: 'change', title: '变更类型 / 当前岗位' },
        { key: 'target', title: '目标企业 / 岗位' },
        { key: 'reason', title: '原因' },
        { key: 'createdAt', title: '申请时间' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '100px' }
      ],
      detailDlg: { visible: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null
    }
  },
  computed: {
    detailItems() {
      const d = this.detailDlg.data || {}
      return [
        { label: '学生', value: d.studentName },
        { label: '变更类型', value: d.changeTypeLabel },
        { label: '当前', value: `${d.currentEnterprise} / ${d.currentPosition}` },
        { label: '目标', value: `${d.targetEnterpriseName || '—'} / ${d.targetPositionName || '—'}` },
        { label: '原因', value: d.reason },
        { label: '审核意见', value: d.reviewComment || '—' }
      ]
    },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, at: t.occurredAt,
        reason: t.detail && (t.detail.comment || '')
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        const map = { pending: 'PENDING', approved: 'APPROVED', rejected: 'REJECTED', all: '' }
        this.filters.status = map[(panel || 'pending').toString()] ?? 'PENDING'
        this.pagination.page = 1
        this.load()
      }
    }
  },
  methods: {
    switchTab(v) {
      const map = { PENDING: 'pending', APPROVED: 'approved', REJECTED: 'rejected', '': 'all' }
      const panel = map[v] || 'all'
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { panel } })
      } else {
        this.filters.status = v
        this.pagination.page = 1
        this.load()
      }
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getChangeRequests({
        status: this.filters.status, page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async openDetail(row) {
      const res = await internshipApi.getChangeRequestDetail(row.id)
      if (res.code !== 0) return toast.error(res.message)
      this.detailDlg = { visible: true, data: res.data }
    },
    openReview(row, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: row.id, action }
      this.cd = {
        visible: true,
        title: ap ? '通过变更申请' : '驳回变更申请',
        content: `${ap ? '通过' : '驳回'}「${row.studentName}」的${row.changeTypeLabel}申请，将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false
      }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await internshipApi.reviewChangeRequest(this.pending.id, {
        action: this.pending.action, comment: reason || ''
      })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message)
      this.cd.visible = false
      toast.success('审核完成')
      this.load()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.modal { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(520px,100%); max-height: 88vh; display: flex; flex-direction: column; }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; }
.mp-link--danger { color: var(--danger-600); }
</style>
