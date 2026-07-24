<template>
  <ModulePageShell
    title="同步任务与失败中心"
    subtitle="登记同步任务 · 失败重试 · 受控取消"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'enqueue', label: '＋ 登记同步任务', variant: 'primary' }]" @action="openEnqueue" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无同步任务" description="可登记手工同步或等待接口自动入队" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-status="{ row }">
          <StatusTag
            :type="row.status === 'SUCCESS' ? 'success' : row.status === 'FAILED' ? 'danger' : 'default'"
            :label="row.statusLabel || row.status"
            dot
          />
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.status === 'FAILED'"
            class="mp-link"
            @click="doRetry(row)"
          >重试</button>
          <button
            v-if="row.status !== 'CANCELLED' && row.status !== 'SUCCESS'"
            class="mp-link mp-link--danger"
            @click="askCancel(row)"
          >取消</button>
          <span v-if="row.status === 'SUCCESS' || row.status === 'CANCELLED'" class="mp-note">—</span>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="form.open" title="登记同步任务">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitEnqueue">登记</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="cancel.open"
      type="danger"
      title="取消该同步任务？"
      :message="'将取消「' + (cancel.row ? cancel.row.name : '') + '」并写入审计。'"
      confirm-text="确认取消"
      require-reason
      reason-label="取消原因"
      :submitting="cancel.submitting"
      @confirm="doCancel"
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
  name: 'SystemSyncJobView',
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
        { key: 'name', title: '任务' },
        { key: 'integrationId', title: '关联连接' },
        { key: 'status', title: '状态' },
        { key: 'message', title: '说明' },
        { key: 'updatedAt', title: '更新时间' },
        { key: 'actions', title: '操作', width: '120px' }
      ],
      form: { open: false, value: { name: '', integrationId: '', forceFail: false }, errors: {}, submitting: false },
      cancel: { open: false, row: null, submitting: false }
    }
  },
  computed: {
    formFields() {
      return [
        { key: 'name', label: '任务名称', required: true },
        { key: 'integrationId', label: '关联连接 ID' },
        { key: 'message', label: '说明', type: 'textarea', full: true }
      ]
    }
  },
  created() { this.load() },
  methods: {
    openEnqueue() {
      this.form = {
        open: true,
        value: { name: '手工同步', integrationId: '', message: '' },
        errors: {},
        submitting: false
      }
    },
    async submitEnqueue() {
      const errors = FormFields.validateRequired(
        this.formFields.filter((f) => f.required),
        this.form.value
      )
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.enqueueSyncJob(this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('同步任务已登记')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doRetry(row) {
      const res = await systemApi.retrySyncJob(row.id)
      if (res.code === 0) {
        toast.success('已重试')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    askCancel(row) {
      this.cancel = { open: true, row, submitting: false }
    },
    async doCancel({ reason }) {
      this.cancel.submitting = true
      const res = await systemApi.cancelSyncJob(this.cancel.row.id, { reason })
      this.cancel.submitting = false
      if (res.code === 0) {
        toast.success('任务已取消')
        this.cancel.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listSyncJobs()
      if (res.code === 0) this.rows = res.data.list || []
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link + .mp-link { margin-left: var(--space-2); }
</style>
