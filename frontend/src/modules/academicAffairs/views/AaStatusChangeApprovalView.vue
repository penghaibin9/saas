<template>
  <ModulePageShell
    title="异动审批"
    subtitle="辅导员初审 → 原学院教务转出 → 目标学院教务接收（转专业）→ 教务处终审，逐级处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无待审学籍异动" description="按当前节点审批范围过滤，处理后从此处移除" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.fromStatus }} → {{ row.toStatus }}</div>
        </template>
        <template #cell-type="{ row }"><StatusTag type="primary" :label="row.changeTypeLabel" dot /></template>
        <template #cell-node="{ row }"><span>{{ nodeLabel(row.currentNode) }}</span></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="askApprove(row)">通过</button>
          <button class="mp-link" style="margin-left: var(--space-2)" @click="askReturn(row)">退回</button>
          <button class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askReject(row)">驳回</button>
          <button class="mp-link" style="margin-left: var(--space-2)" @click="goDetail(row)">详情</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible" :title="dlg.title" :message="dlg.message"
      :type="dlg.type" :confirm-text="dlg.confirmText" :require-reason="dlg.requireReason"
      reason-label="审批意见" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 学籍异动审批工作台（Tier1「异动审批」，/admin/academic-affairs/status-changes/approval）。
 * 复用既有 GET /status-changes（后端已按 COUNSELOR_REVIEW/COLLEGE_REVIEW/OUT_COLLEGE_REVIEW/
 * IN_COLLEGE_REVIEW/AA_OFFICE_FINAL 节点权限与数据范围收敛，见 academic_affairs_change_service.
 * _check_node_authority）+ POST /status-changes/{id}/review（APPROVE/RETURN/REJECT 三态，与
 * 「异动详情」页内审批操作同一后端入口，不新造审批状态机）。
 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TYPE_LABEL, STATUS_LABEL, NODE_LABEL } from '@/modules/academicAffairs/constants/status-change'
import { toast } from '@/utils/toast'

const PENDING = ['SUBMITTED', 'IN_REVIEW']
const EMPTY = () => ({ changeType: '' })

export default {
  name: 'AaStatusChangeApprovalView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 20, filters: EMPTY(),
      dlg: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, action: '', row: null },
      columns: [
        { key: 'student', title: '学生 / 状态变化' },
        { key: 'type', title: '类型' },
        { key: 'node', title: '当前节点' },
        { key: 'actions', title: '操作', width: '220px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [{ key: 'changeType', label: '类型', type: 'select', options: Object.keys(TYPE_LABEL).map((v) => ({ value: v, label: TYPE_LABEL[v] })) }]
    }
  },
  created() { this.load() },
  methods: {
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    async load() {
      this.loading = true; this.error = ''
      const res = await academicAffairsApi.getStatusChanges({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) {
        // 后端已按节点权限 + 数据范围过滤到「与我相关」的异动；前端再收敛为在途待处理
        this.rows = res.data.list.filter((r) => PENDING.includes(r.status))
        this.total = this.rows.length
      } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
    askApprove(row) {
      const isFinal = !NODE_LABEL[row.currentNode] || row.currentNode === 'AA_OFFICE_FINAL'
      this.dlg = { visible: true, title: `通过「${row.changeTypeLabel}」`, action: 'APPROVE', row,
        type: 'primary', confirmText: '确认通过', requireReason: false,
        message: isFinal ? '这是终审节点，通过后异动将即刻生效并写入学籍主档。' : '通过后流转到下一审批节点。' }
    },
    askReturn(row) {
      this.dlg = { visible: true, title: '退回异动', action: 'RETURN', row,
        type: 'warning', confirmText: '确认退回', requireReason: true, message: '退回给申请方修改，请填写退回原因（≥5 字）。' }
    },
    askReject(row) {
      this.dlg = { visible: true, title: '驳回异动', action: 'REJECT', row,
        type: 'danger', confirmText: '确认驳回', requireReason: true, message: '驳回后本异动终止，请填写驳回原因（≥5 字）。' }
    },
    async onConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      this.submitting = true
      try {
        const res = await academicAffairsApi.reviewStatusChange(this.dlg.row.changeId, this.dlg.action, reason)
        if (res.code === 0) {
          toast.success('已处理')
          this.dlg.visible = false
          this.load()
        } else toast.error(res.message || '处理失败')
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link--danger { color: var(--danger-600, #f53f3f); }
</style>
