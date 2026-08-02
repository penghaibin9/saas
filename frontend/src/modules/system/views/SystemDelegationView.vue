<template>
  <ModulePageShell
    title="临时授权与工作移交"
    subtitle="创建临时授权 · 到期自动回收 · 可提前回收并留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 创建临时授权', variant: 'primary' }]" @action="openCreate" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无临时授权" description="可创建受控临时授权，到期后自动回收" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'REVOKED' ? 'warning' : 'default'" :label="row.statusLabel || row.status" dot />
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.status === 'ACTIVE'"
            class="mp-link mp-link--danger"
            @click="askRevoke(row)"
          >回收</button>
          <span v-else class="mp-note">—</span>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="form.open" title="创建临时授权" mode="modal" size="medium">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitCreate">创建并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="revoke.open"
      type="danger"
      title="回收该临时授权？"
      :message="'将立即回收 ' + (revoke.row ? revoke.row.granteeUserNo : '') + ' 的临时角色授权。'"
      confirm-text="确认回收"
      require-reason
      reason-label="回收原因"
      :submitting="revoke.submitting"
      @confirm="doRevoke"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemDelegationView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppConfirmDialog, FormFields
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      columns: [
        { key: 'granteeUserNo', title: '受权人工号' },
        { key: 'roleCode', title: '临时角色' },
        { key: 'expiresAt', title: '到期时间' },
        { key: 'reason', title: '原因' },
        { key: 'status', title: '状态' },
        { key: 'createdAt', title: '创建时间' },
        { key: 'actions', title: '操作', width: '80px' }
      ],
      form: {
        open: false,
        value: { granteeUserNo: '', roleCode: '', expiresAt: '', reason: '' },
        errors: {},
        submitting: false
      },
      revoke: { open: false, row: null, submitting: false }
    }
  },
  computed: {
    formFields() {
      return [
        { key: 'granteeUserNo', label: '受权人工号', required: true },
        { key: 'roleCode', label: '临时角色编码', required: true, placeholder: '如 COUNSELOR' },
        { key: 'expiresAt', label: '到期时间', required: true, placeholder: 'YYYY-MM-DD HH:mm:ss' },
        { key: 'reason', label: '授权原因', type: 'textarea', required: true, full: true, hint: '不少于 5 个字' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    openCreate() {
      this.form = {
        open: true,
        value: { granteeUserNo: '', roleCode: '', expiresAt: '', reason: '' },
        errors: {},
        submitting: false
      }
    },
    async submitCreate() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.createDelegation(this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('临时授权已创建')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    askRevoke(row) {
      this.revoke = { open: true, row, submitting: false }
    },
    async doRevoke({ reason }) {
      this.revoke.submitting = true
      const res = await systemApi.revokeDelegation(this.revoke.row.id, { reason })
      this.revoke.submitting = false
      if (res.code === 0) {
        toast.success('临时授权已回收')
        this.revoke.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listDelegations()
      if (res.code === 0) this.rows = res.data.list || []
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
