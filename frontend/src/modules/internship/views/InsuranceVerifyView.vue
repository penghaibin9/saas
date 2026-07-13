<template>
  <ModulePageShell title="实习保险核验" subtitle="学生小程序提交保单 · 学校核验通过后方可到岗"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint">
    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>
    <DataTable :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag></template>
      <template #cell-actions="{ row }">
        <template v-if="row.status === 'PENDING_VERIFY'">
          <AppPermissionButton :allowed="canVerify" code="internship.insurance.verify" variant="secondary" size="sm" @click="openVerify(row, 'APPROVE')">通过</AppPermissionButton>
          <AppPermissionButton :allowed="canVerify" code="internship.insurance.verify" variant="ghost" size="sm" :danger="true" @click="openVerify(row, 'REJECT')">驳回</AppPermissionButton>
        </template>
        <span v-else class="muted">—</span>
      </template>
    </DataTable>
    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :require-reason="cd.requireReason" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppSearchBox, AppQuickFilterChips, AppPermissionButton } from '@/components/common'
import { insuranceApi } from '@/modules/internship/api/plan-insurance.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

export default {
  name: 'InsuranceVerifyView',
  components: { ModulePageShell, DataTable, AppStatusTag, AppConfirmDialog, AppSearchBox, AppQuickFilterChips, AppPermissionButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      rows: [], loading: false, keyword: '', statusFilter: 'PENDING_VERIFY', page: 1, pageSize: 20, total: 0,
      columns: [
        { key: 'studentName', title: '姓名' }, { key: 'studentNo', title: '学号' },
        { key: 'enterpriseName', title: '企业' }, { key: 'insurerName', title: '承保单位' },
        { key: 'policyNo', title: '保单号' }, { key: 'effectiveDate', title: '生效' },
        { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '140px' }
      ],
      statusOptions: [
        { label: '待核验', value: 'PENDING_VERIFY' }, { label: '已核验', value: 'VERIFIED' },
        { label: '已驳回', value: 'REJECTED' }, { label: '未提交', value: 'NOT_SUBMITTED' }
      ],
      cd: { visible: false, title: '', content: '', danger: false, requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    canVerify() { return canCode(this.ctx, 'internship.insurance.verify') }
  },
  created() { this.load() },
  methods: {
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await insuranceApi.getInsurances(params)
      this.loading = false
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
    },
    openVerify(row, action) {
      if (!this.canVerify) return toast.error('无实习保险核验权限')
      this.pending = { id: row.id, action }
      const ap = action === 'APPROVE'
      this.cd = {
        visible: true, title: ap ? '保险核验通过' : '保险核验驳回',
        content: `${ap ? '通过' : '驳回'}「${row.studentName}」的实习保险`,
        danger: !ap, requireReason: !ap, submitting: false
      }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await insuranceApi.verify(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message)
      this.cd.visible = false
      toast.success('核验完成')
      this.load()
    }
  }
}
</script>

<style scoped>
.bar { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.muted { color: var(--text-tertiary); font-size: var(--font-size-sm); }
</style>
