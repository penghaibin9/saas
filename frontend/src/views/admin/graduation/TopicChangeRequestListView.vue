<template>
  <ModulePageShell
    title="题目调整（选题变更申请）"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无变更申请" description="学生获批题目后如需换题，须发起「课题信息变更」申请，审核通过后生效" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-change="{ row }">
          <div class="mp-cell-main">{{ row.oldTopicTitle }} → {{ row.newTopicTitle }}</div>
          <div class="mp-cell-sub">{{ row.reason }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" style="margin-left: var(--space-2)" @click="askApprove(row)">通过</button>
            <button class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askReject(row)">驳回</button>
          </template>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="detailVisible" title="变更申请详情">
      <div v-if="detail" class="tc-detail">
        <dl class="tc-meta">
          <div><dt>学生</dt><dd>{{ detail.studentName }}（{{ detail.studentNo }}）</dd></div>
          <div><dt>原题目</dt><dd>{{ detail.oldTopicTitle }} · 导师 {{ detail.oldAdvisorName || '—' }}</dd></div>
          <div><dt>目标题目</dt><dd>{{ detail.newTopicTitle }} · 导师 {{ detail.newAdvisorName || '—' }}</dd></div>
          <div><dt>变更理由</dt><dd>{{ detail.reason }}</dd></div>
          <div><dt>状态</dt><dd><StatusTag :type="detail.statusTone" :label="detail.statusLabel" dot /></dd></div>
          <div v-if="detail.reviewComment"><dt>审核意见</dt><dd>{{ detail.reviewComment }}</dd></div>
          <div v-if="detail.reviewerName"><dt>审核人</dt><dd>{{ detail.reviewerName }} · {{ detail.reviewedAt }}</dd></div>
          <div><dt>发起人</dt><dd>{{ detail.requestedBy }} · {{ detail.requestedAt }}</dd></div>
        </dl>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 题目调整/选题变更申请审核（/admin/graduation/topic-changes）：
 * 学生获批题目后换题的唯一合法途径——发起变更申请→教师/管理员重新审核（通过即迁移分配，驳回须≥5字理由）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { gdTopicChangeApi } from '@/modules/graduation/api/graduation-topic-change.api'
import { toast } from '@/utils/toast'

const STATUS_OPTS = [
  { value: 'PENDING', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'CANCELLED', label: '已撤销' }
]
const EMPTY_FILTERS = () => ({ status: '' })

export default {
  name: 'TopicChangeRequestListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      detailVisible: false, detail: null,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '理由', action: null, row: null }
    }
  },
  computed: {
    filterFields() {
      return [{ key: 'status', label: '状态', type: 'select', options: STATUS_OPTS }]
    },
    toolbarActions() {
      return [{ key: 'refresh', label: '刷新' }]
    },
    columns() {
      return [
        { key: 'student', title: '学生' },
        { key: 'change', title: '变更（原题目 → 目标题目）' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    },
    pageSubtitle() {
      return `共 ${this.total} 条变更申请 · 通过即迁移选题分配，驳回须说明理由`
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await gdTopicChangeApi.getChangeRequests({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) { if (key === 'refresh') this.load() },
    async openDetail(row) {
      const res = await gdTopicChangeApi.getChangeRequestDetail(row.id)
      if (res.code === 0) { this.detail = res.data; this.detailVisible = true } else toast.error(res.message)
    },
    askApprove(row) {
      this.confirm = { visible: true, title: '通过变更申请', message: `确认通过「${row.studentName}」由「${row.oldTopicTitle}」变更至「${row.newTopicTitle}」？将立即迁移选题分配。`, type: 'primary', confirmText: '通过', requireReason: false, action: 'APPROVE', row }
    },
    askReject(row) {
      this.confirm = { visible: true, title: '驳回变更申请', message: `驳回「${row.studentName}」的变更申请？`, type: 'danger', confirmText: '驳回', requireReason: true, reasonLabel: '驳回理由', action: 'REJECT', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        const res = await gdTopicChangeApi.reviewChangeRequest(row.id, { action, comment: reason || '' })
        if (res.code === 0) { toast.success('已处理并写入留痕'); this.confirm.visible = false; this.load() } else toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link--danger { color: var(--danger, #dc2626); }
.tc-meta { display: grid; grid-template-columns: 1fr; gap: 10px; }
.tc-meta dt { font-size: 12px; color: var(--t3, #64748b); }
.tc-meta dd { margin: 2px 0 0; font-size: 13px; }
</style>
