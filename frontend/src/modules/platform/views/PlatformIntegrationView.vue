<template>
  <ModulePageShell
    title="集成开放管理"
    :subtitle="'共 ' + pagination.total + ' 个外部系统接入 · 凭证密文存储，页面不展示明文'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的集成" description="所有外部系统必须先注册再调用（集成十条铁律）" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-integration="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.typeLabel }} · {{ row.tenantName }}</div>
        </template>
        <template #cell-authType="{ row }">
          <span class="mp-cell-sub">{{ row.authType }}</span>
        </template>
        <template #cell-health="{ row }">
          <StatusTag :type="row.health === 'HEALTHY' ? 'success' : row.health === 'WARNING' ? 'warning' : 'danger'" :label="row.healthLabel" dot />
        </template>
        <template #cell-calls="{ row }">
          <div class="mp-cell-main">{{ row.todayCalls.toLocaleString() }}</div>
          <div class="mp-cell-sub" :class="{ 'ig-fail': row.failCalls > 0 }">失败 {{ row.failCalls }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('testIntegration') }" :title="reason('testIntegration')" @click="doTest(row)">测试连接</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('editIntegration') }" :title="reason('editIntegration')" @click="openEdit(row)">编辑</button>
          <button
            v-if="row.status === 'ENABLED'"
            class="mp-link ig-danger"
            :class="{ 'is-disabled': !can('disableIntegration') }"
            :title="reason('disableIntegration')"
            @click="askDisable(row)"
          >停用</button>
          <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableIntegration') }" @click="doEnable(row)">启用</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑集成 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑集成' : '新增外部系统接入'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">
        保存后 AppKey / Secret 通过安全信道一次性下发对接责任人，系统仅存密文；全部对接调用写入调用日志。
      </p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <!-- 集成详情 -->
    <AppDrawer v-model:visible="detail.open" :title="'集成详情 · ' + (detail.data ? detail.data.name : '')">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv"><span class="mp-kv__k">租户</span><span class="mp-kv__v">{{ detail.data.tenantName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">接入地址</span><span class="mp-kv__v">{{ detail.data.endpoint }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">认证方式</span><span class="mp-kv__v">{{ detail.data.authType }} · {{ detail.data.signAlg }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">AppKey</span><span class="mp-kv__v"><SecretField :masked="detail.data.appKeyMasked" /></span></div>
        <div class="mp-kv"><span class="mp-kv__k">AppSecret</span><span class="mp-kv__v"><SecretField :masked="detail.data.secretMasked" /></span></div>
        <div class="mp-kv"><span class="mp-kv__k">IP 白名单</span><span class="mp-kv__v">{{ (detail.data.ipWhitelist || []).join('、') || '未配置' }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">超时</span><span class="mp-kv__v">{{ detail.data.timeoutMs }} ms</span></div>

        <h4 class="ig-sec">健康检查</h4>
        <EmptyState v-if="!detail.data.healthChecks.length" title="暂无检查记录" description="点击列表中的「测试连接」执行健康检查" />
        <div v-for="c in detail.data.healthChecks" :key="c.item" class="mp-kv">
          <span class="mp-kv__k">{{ c.item }}</span>
          <span class="mp-kv__v">
            <StatusTag :type="c.result === 'HEALTHY' ? 'success' : c.result === 'WARNING' ? 'warning' : 'danger'" :label="c.resultLabel" />
            <span class="mp-note" style="margin-left: var(--space-2)">{{ c.detail }}</span>
          </span>
        </div>

        <h4 class="ig-sec">最近错误</h4>
        <EmptyState v-if="!detail.data.recentErrors.length" title="暂无错误" description="最近调用均正常" />
        <ul v-else class="mp-timeline">
          <li v-for="(e, i) in detail.data.recentErrors" :key="i" class="mp-timeline__item is-danger">
            <div class="mp-timeline__title">{{ e.codeText }}</div>
            <div class="mp-timeline__desc">{{ e.message }}</div>
            <div class="mp-timeline__time">{{ e.time }}</div>
          </li>
        </ul>

        <h4 class="ig-sec">操作留痕</h4>
        <table class="mp-audit">
          <thead><tr><th>操作人</th><th>动作</th><th>影响</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(a, i) in detail.data.auditTrail" :key="i">
              <td class="is-who">{{ a.who }}</td><td>{{ a.action }}</td><td>{{ a.affected }}</td><td>{{ a.time }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDisable"
      type="danger"
      :title="'停用集成「' + (disableRow ? disableRow.name : '') + '」？'"
      message="停用后该系统调用即时拦截；配置、映射与历史日志完整保留，可随时恢复。"
      confirm-text="确认停用并留痕"
      require-reason
      reason-label="停用原因"
      :submitting="disableSubmitting"
      @confirm="doDisable"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 集成开放管理（/admin/platform/integrations）：
 * 外部系统注册 / 编辑 / 停用启用留痕 / 测试连接（健康检查）/ 详情（凭证脱敏 + 错误 + 留痕）/ 导出配置。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/platform/components/FormFields.vue'
import SecretField from '@/modules/platform/components/SecretField.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', health: '', status: '' })

export default {
  name: 'PlatformIntegrationView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, FormFields, SecretField
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'integration', title: '外部系统' },
        { key: 'authType', title: '认证方式' },
        { key: 'health', title: '健康状态' },
        { key: 'calls', title: '今日调用' },
        { key: 'lastCallAt', title: '最后调用' },
        { key: 'owner', title: '责任人' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '230px' }
      ],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      detail: { open: false, loading: false, data: null },
      confirmDisable: false,
      disableRow: null,
      disableSubmitting: false
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '系统名称 / 租户' },
        { key: 'type', label: '系统类型', type: 'select', options: o.filterOptions.integrationTypes },
        { key: 'health', label: '健康状态', type: 'select', options: o.statusOptions.integrationHealth },
        { key: 'status', label: '启用状态', type: 'select', options: o.statusOptions.enableStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createIntegration', label: '＋ 新增集成', variant: 'primary' },
        { key: 'exportIntegrations', label: '⇩ 导出集成配置' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '系统名称', required: true, placeholder: '如：教务系统对接' },
        { key: 'type', label: '系统类型', type: 'select', required: true, options: this.ctx.filterOptions.integrationTypes },
        { key: 'tenantName', label: '所属租户', placeholder: '留空为平台公共通道' },
        { key: 'authType', label: '认证方式', type: 'select', options: [
          { value: 'AppKey + 签名', label: 'AppKey + 签名' },
          { value: 'OAuth2 / OIDC', label: 'OAuth2 / OIDC' },
          { value: 'AccessKey（已加密）', label: 'AccessKey' }
        ] },
        { key: 'owner', label: '责任人' },
        { key: 'endpoint', label: '接入地址', full: true, placeholder: 'https://...' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.load()
    },
    async onToolbar(key) {
      if (key === 'createIntegration') this.openEdit(null)
      if (key === 'exportIntegrations') {
        const res = await platformApi.exportIntegrations()
        if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（不含密钥明文），已留痕')
      }
    },
    openEdit(row) {
      const key = row ? 'editIntegration' : 'createIntegration'
      if (!this.can(key)) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row ? { name: row.name, type: row.type, tenantName: row.tenantName, authType: row.authType, owner: row.owner, endpoint: '' } : { name: '', type: '', tenantName: '', authType: 'AppKey + 签名', owner: '', endpoint: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await platformApi.saveIntegration({ id: this.form.id || undefined, ...this.form.value })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success((this.form.id ? '集成已更新' : '集成已登记，凭证一次性下发') + '，已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      if (!this.can('viewIntegrationLogs')) return
      this.detail = { open: true, loading: true, data: null }
      const res = await platformApi.getIntegrationDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
    },
    async doTest(row) {
      if (!this.can('testIntegration')) return
      const res = await platformApi.testIntegration(row.id)
      if (res.code === 0) {
        const fn = res.data.health === 'HEALTHY' ? 'success' : res.data.health === 'WARNING' ? 'warning' : 'error'
        toast[fn]('健康检查（' + row.name + '）：' + res.data.message + '，结果已留痕')
      }
    },
    askDisable(row) {
      if (!this.can('disableIntegration')) return
      this.disableRow = row
      this.confirmDisable = true
    },
    async doDisable({ reason }) {
      this.disableSubmitting = true
      const res = await platformApi.setIntegrationStatus(this.disableRow.id, { action: 'DISABLE', reason })
      this.disableSubmitting = false
      if (res.code === 0) {
        toast.success('集成已停用（配置与日志保留），原因已留痕')
        this.confirmDisable = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doEnable(row) {
      if (!this.can('disableIntegration')) return
      const res = await platformApi.setIntegrationStatus(row.id, { action: 'ENABLE' })
      if (res.code === 0) {
        toast.success('集成已恢复启用，已留痕')
        this.load()
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformApi.getIntegrations({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ig-fail {
  color: var(--danger-600);
}
.ig-danger {
  color: var(--danger-600);
}
.ig-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
