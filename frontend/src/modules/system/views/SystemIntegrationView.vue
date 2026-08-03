<template>
  <ModulePageShell
    title="接口、凭证与 Webhook"
    subtitle="本校已授权连接维护 · 凭证加密存储 · 轮换可审计"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 新建连接', variant: 'primary' }]" @action="openForm(null)" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无接口连接" description="可新增本校已授权的接口或 Webhook 连接" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.statusLabel || row.status" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openForm(row)">编辑</button>
          <button class="mp-link" @click="openRotate(row)">轮换凭证</button>
          <button class="mp-link" @click="testConnection(row)">测试连接</button>
        </template>
      </DataTable>
    </div>

    <div class="mp-stack ig-sync">
      <h3 class="ig-sync__title">同步任务</h3>
      <DataTable v-if="syncJobs.length" :columns="syncColumns" :rows="syncJobs" row-key="id">
        <template #cell-status="{ row }">
          <StatusTag :type="syncStatusTone(row.status)" :label="row.statusLabel || row.status" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'FAILED'" class="mp-link" @click="retrySync(row)">重试</button>
          <button v-if="row.status !== 'CANCELLED' && row.status !== 'SUCCESS'" class="mp-link" @click="cancelSync(row)">取消</button>
        </template>
      </DataTable>
      <EmptyState v-else title="暂无同步任务" description="" />
    </div>

    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑接口连接' : '新建接口连接'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="rotate.open" :title="'轮换凭证 · ' + rotate.name">
      <label class="ig-label">新凭证（至少 8 位）</label>
      <textarea v-model="rotate.credential" class="mp-textarea" rows="2" />
      <template #footer>
        <AppButton variant="ghost" @click="rotate.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="rotate.submitting" @click="submitRotate">确认轮换</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemIntegrationView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, FormFields
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      columns: [
        { key: 'name', title: '连接名称' },
        { key: 'endpoint', title: '接口地址' },
        { key: 'authType', title: '认证方式' },
        { key: 'credentialMasked', title: '凭证（脱敏）' },
        { key: 'status', title: '状态' },
        { key: 'updatedAt', title: '更新时间' },
        { key: 'actions', title: '操作', width: '140px' }
      ],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      rotate: { open: false, id: '', name: '', credential: '', submitting: false },
      syncJobs: [],
      syncColumns: [
        { key: 'name', title: '任务名称' },
        { key: 'adapterCode', title: '适配器' },
        { key: 'status', title: '状态' },
        { key: 'message', title: '说明' },
        { key: 'actions', title: '操作', width: '120px' }
      ]
    }
  },
  computed: {
    formFields() {
      return [
        { key: 'name', label: '连接名称', required: true },
        { key: 'endpoint', label: '接口地址', required: true, full: true },
        { key: 'authType', label: '认证方式', placeholder: 'TOKEN / BASIC / WEBHOOK' },
        { key: 'credential', label: '凭证（新建或覆盖）', type: 'textarea', full: true, hint: '编辑时留空表示不改动凭证' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    openForm(row) {
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row
          ? { name: row.name, endpoint: row.endpoint, authType: row.authType || 'TOKEN', credential: '' }
          : { name: '', endpoint: '', authType: 'TOKEN', credential: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(
        this.formFields.filter((f) => f.key !== 'credential' && f.key !== 'authType'),
        this.form.value
      )
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.saveIntegration({ id: this.form.id || undefined, ...this.form.value })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('接口连接已保存')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openRotate(row) {
      this.rotate = { open: true, id: row.id, name: row.name, credential: '', submitting: false }
    },
    async submitRotate() {
      this.rotate.submitting = true
      const res = await systemApi.rotateIntegration(this.rotate.id, { credential: this.rotate.credential })
      this.rotate.submitting = false
      if (res.code === 0) {
        toast.success('凭证已轮换')
        this.rotate.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    syncStatusTone(s) {
      return { PENDING: 'default', RUNNING: 'warning', SUCCESS: 'success', FAILED: 'danger', CANCELLED: 'default' }[s] || 'default'
    },
    async testConnection(row) {
      const res = await systemApi.testIntegration(row.id)
      if (res.code === 0) toast.success(res.data?.message || '测试完成')
      else toast.error(res.message)
      this.load()
    },
    async retrySync(row) {
      const res = await systemApi.retrySyncJob(row.id)
      if (res.code === 0) { toast.success('已重试'); this.loadSyncJobs() }
      else toast.error(res.message)
    },
    async cancelSync(row) {
      const res = await systemApi.cancelSyncJob(row.id, { reason: '管理员在接口治理页取消' })
      if (res.code === 0) { toast.success('已取消'); this.loadSyncJobs() }
      else toast.error(res.message)
    },
    async loadSyncJobs() {
      const res = await systemApi.listSyncJobs()
      if (res.code === 0) this.syncJobs = res.data.list || res.data.items || []
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listIntegrations()
      if (res.code === 0) this.rows = res.data.list || []
      else this.error = res.message
      this.loading = false
      await this.loadSyncJobs()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ig-label {
  display: block;
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-1);
}
.mp-link + .mp-link { margin-left: var(--space-2); }
</style>
