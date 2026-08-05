<template>
  <ModulePageShell
    title="API 访问 / Webhook 管理"
    subtitle="开放应用授权 · 事件订阅 · 密钥仅存密文，重置需双人复核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'api' }" @click="tab = 'api'">API 访问配置</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'webhook' }" @click="switchWebhook">Webhook 订阅</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <!-- ===== API 应用 ===== -->
      <template v-else-if="tab === 'api'">
        <EmptyState v-if="!rows.length" title="暂无 API 访问配置" description="外部系统调用开放 API 前必须先创建应用并授权范围" />
        <DataTable v-else :columns="apiColumns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
          <template #cell-app="{ row }">
            <div class="mp-cell-main">{{ row.appName }}</div>
            <div class="mp-cell-sub">{{ row.tenantName }}</div>
          </template>
          <template #cell-appKey="{ row }">
            <SecretField :masked="row.appKeyMasked" />
          </template>
          <template #cell-scopes="{ row }">
            <div class="mp-cell-main">{{ row.apiScopes.join('、') }}</div>
            <div class="mp-cell-sub">{{ row.dataScopeLabel }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-link" @click="openApiDetail(row)">查看</button>
            <button class="mp-link" :class="{ 'is-disabled': !can('editApiAccess') }" :title="reason('editApiAccess')" @click="openApiEdit(row)">编辑</button>
            <button class="mp-link" :class="{ 'is-disabled': !can('resetApiSecret') }" :title="reason('resetApiSecret')" @click="askResetSecret(row)">重置密钥</button>
            <button
              v-if="row.status === 'ENABLED'"
              class="mp-link aa-danger"
              :class="{ 'is-disabled': !can('disableApiAccess') }"
              :title="reason('disableApiAccess')"
              @click="askDisableApi(row)"
            >停用</button>
            <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableApiAccess') }" @click="doEnableApi(row)">启用</button>
          </template>
        </DataTable>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">最近调用日志</span>
            <button class="mp-link" :class="{ 'is-disabled': !can('exportApiLogs') }" :title="reason('exportApiLogs')" @click="doExportLogs">⇩ 导出调用日志</button>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th>时间</th><th>应用</th><th>接口</th><th>状态码</th><th>耗时</th><th>结果</th></tr></thead>
              <tbody>
                <tr v-for="l in callLogs" :key="l.id">
                  <td>{{ l.time }}</td>
                  <td class="is-who">{{ l.appName }}</td>
                  <td>{{ l.api }}</td>
                  <td :class="{ 'aa-fail': l.status >= 400 }">{{ l.status }}</td>
                  <td>{{ l.costMs }} ms</td>
                  <td>{{ l.resultLabel }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <!-- ===== Webhook ===== -->
      <template v-else>
        <EmptyState v-if="!webhooks.length" title="暂无 Webhook 订阅" description="外部系统可订阅学生 / 毕设 / 实习 / 流程事件" />
        <DataTable v-else :columns="whColumns" :rows="webhooks" row-key="id">
          <template #cell-hook="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">{{ row.tenantName }} · {{ row.urlMasked }}</div>
          </template>
          <template #cell-events="{ row }">
            <code v-for="e in row.events" :key="e" class="aa-event">{{ e }}</code>
          </template>
          <template #cell-signKey="{ row }">
            <SecretField :masked="row.signKeyMasked" />
          </template>
          <template #cell-lastDelivery="{ row }">
            <div class="mp-cell-sub" :class="{ 'aa-fail': row.failCount24h > 0 }">{{ row.lastDelivery }}</div>
            <div v-if="row.failCount24h" class="mp-cell-sub aa-fail">24h 失败 {{ row.failCount24h }} 次</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-link" :class="{ 'is-disabled': !can('redeliverWebhook') }" :title="reason('redeliverWebhook')" @click="doRedeliver(row)">手动重推</button>
            <button class="mp-link" :class="{ 'is-disabled': !can('editWebhook') }" :title="reason('editWebhook')" @click="openWebhookEdit(row)">编辑</button>
            <button
              v-if="row.status === 'ENABLED'"
              class="mp-link aa-danger"
              :class="{ 'is-disabled': !can('disableWebhook') }"
              :title="reason('disableWebhook')"
              @click="askDisableWebhook(row)"
            >停用</button>
            <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableWebhook') }" @click="doEnableWebhook(row)">启用</button>
          </template>
        </DataTable>
        <p class="mp-note">投递失败按重试策略自动补偿；连续失败将触发告警并可手动重推，全部投递有日志。</p>
      </template>
    </div>

    <!-- API 应用 新增/编辑 -->
    <AppDrawer v-model:visible="apiForm.open" :title="apiForm.id ? '编辑 API 访问配置' : '新增 API 访问配置'" mode="modal" size="medium">
      <FormFields v-model="apiForm.value" :fields="apiFormFields" :errors="apiForm.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">创建后 AppSecret 仅一次性下发；数据范围授权遵循最小可用原则，敏感字段仅提供脱敏档。</p>
      <template #footer>
        <AppButton variant="ghost" @click="apiForm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="apiForm.submitting" @click="submitApiForm">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <!-- API 应用详情 -->
    <AppDrawer v-model:visible="apiDetail.open" :title="'访问配置 · ' + (apiDetail.row ? apiDetail.row.appName : '')" mode="modal" size="large">
      <template v-if="apiDetail.row">
        <div class="mp-kv"><span class="mp-kv__k">租户</span><span class="mp-kv__v">{{ apiDetail.row.tenantName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">AppKey</span><span class="mp-kv__v"><SecretField :masked="apiDetail.row.appKeyMasked" /></span></div>
        <div class="mp-kv"><span class="mp-kv__k">AppSecret</span><span class="mp-kv__v"><SecretField :masked="apiDetail.row.secretMasked" /></span></div>
        <div class="mp-kv"><span class="mp-kv__k">授权接口</span><span class="mp-kv__v">{{ apiDetail.row.apiScopes.join('、') }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ apiDetail.row.dataScopeLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">IP 白名单</span><span class="mp-kv__v">{{ apiDetail.row.ipWhitelist }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">有效期至</span><span class="mp-kv__v">{{ apiDetail.row.validUntil }}</span></div>
        <p class="mp-note" style="margin-top: var(--space-3)">调用链路：验签 → 限流 → 权限校验 → 数据范围过滤 → 返回 → 记录日志；越权请求返回 403 并留痕。</p>
      </template>
    </AppDrawer>

    <!-- Webhook 新增/编辑 -->
    <AppDrawer v-model:visible="whForm.open" :title="whForm.id ? '编辑 Webhook 订阅' : '新增 Webhook 订阅'" mode="modal" size="medium">
      <FormFields v-model="whForm.value" :fields="whFormFields" :errors="whForm.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="whForm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="whForm.submitting" @click="submitWebhookForm">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmReset"
      type="danger"
      :title="'重置「' + (actionRow ? actionRow.appName : '') + '」的密钥？'"
      message="旧密钥立即失效，可能造成对接方调用中断；新密钥通过安全信道一次性下发，页面不展示明文。该操作需双人复核。"
      confirm-text="确认重置密钥"
      require-reason
      reason-label="重置原因"
      :submitting="confirmSubmitting"
      @confirm="doResetSecret"
    />
    <AppConfirmDialog
      v-model:visible="confirmDisableApi"
      type="danger"
      :title="'停用「' + (actionRow ? actionRow.appName : '') + '」的 API 访问？'"
      message="停用后调用即时返回 403；配置与调用日志保留，可随时恢复。"
      confirm-text="确认停用并留痕"
      require-reason
      reason-label="停用原因"
      :submitting="confirmSubmitting"
      @confirm="doDisableApi"
    />
    <AppConfirmDialog
      v-model:visible="confirmDisableWebhook"
      type="danger"
      :title="'停用 Webhook「' + (actionRow ? actionRow.name : '') + '」？'"
      message="停止事件投递；历史投递日志保留。"
      confirm-text="确认停用并留痕"
      require-reason
      reason-label="停用原因"
      :submitting="confirmSubmitting"
      @confirm="doDisableWebhook"
    />
  </ModulePageShell>
</template>

<script>
/**
 * API 访问 / Webhook 管理（/admin/platform/api-access）：
 * API 应用（创建/编辑/重置密钥双人复核/停用/调用日志/导出）+ Webhook（订阅/重推/停用），密钥全程脱敏。
 */
import {
  ModulePageShell, ModuleToolbar, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/platform/components/FormFields.vue'
import SecretField from '@/modules/platform/components/SecretField.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformApiAccessView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, FormFields, SecretField
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'api',
      loading: true,
      error: '',
      rows: [],
      callLogs: [],
      webhooks: [],
      pagination: { page: 1, pageSize: 10, total: 0 },
      apiColumns: [
        { key: 'app', title: '应用' },
        { key: 'appKey', title: 'AppKey（脱敏）' },
        { key: 'scopes', title: '授权范围' },
        { key: 'ipWhitelist', title: 'IP 白名单' },
        { key: 'validUntil', title: '有效期至' },
        { key: 'todayCalls', title: '今日调用' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '230px' }
      ],
      whColumns: [
        { key: 'hook', title: '订阅' },
        { key: 'events', title: '事件' },
        { key: 'signKey', title: '签名密钥' },
        { key: 'retryPolicy', title: '重试策略' },
        { key: 'lastDelivery', title: '最近投递' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '190px' }
      ],
      apiForm: { open: false, id: '', value: {}, errors: {}, submitting: false },
      apiDetail: { open: false, row: null },
      whForm: { open: false, id: '', value: {}, errors: {}, submitting: false },
      confirmReset: false,
      confirmDisableApi: false,
      confirmDisableWebhook: false,
      actionRow: null,
      confirmSubmitting: false
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = this.tab === 'api'
        ? [{ key: 'createApiAccess', label: '＋ 新增 API 访问配置', variant: 'primary' }]
        : [{ key: 'createWebhook', label: '＋ 新增 Webhook 订阅', variant: 'primary' }]
      return list
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    apiFormFields() {
      return [
        { key: 'appName', label: '应用名称', required: true },
        { key: 'tenantName', label: '所属租户', placeholder: '留空为平台公共通道' },
        { key: 'dataScopeLabel', label: '数据范围说明', full: true, placeholder: '如：本校学生基础字段（脱敏档）' },
        { key: 'ipWhitelist', label: 'IP 白名单', full: true, placeholder: '如 10.24.*.*' },
        { key: 'validUntil', label: '有效期至', placeholder: 'YYYY-MM-DD' }
      ]
    },
    whFormFields() {
      return [
        { key: 'name', label: '订阅名称', required: true },
        { key: 'tenantName', label: '所属租户' },
        { key: 'url', label: '回调地址', full: true, required: !this.whForm.id, placeholder: 'https://...（保存后脱敏展示）', disabled: !!this.whForm.id, lockNote: this.whForm.id ? '（地址变更请停用后新建）' : '' },
        { key: 'retryPolicy', label: '重试策略', type: 'select', options: [
          { value: '指数退避 · 最多 5 次', label: '指数退避 · 最多 5 次' },
          { value: '固定间隔 5 分钟 · 最多 3 次', label: '固定间隔 5 分钟 · 最多 3 次' }
        ] }
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
    onToolbar(key) {
      if (key === 'createApiAccess') this.openApiEdit(null)
      if (key === 'createWebhook') this.openWebhookEdit(null)
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async switchWebhook() {
      this.tab = 'webhook'
      const res = await platformApi.getWebhooks()
      if (res.code === 0) this.webhooks = res.data.list
    },
    openApiEdit(row) {
      const key = row ? 'editApiAccess' : 'createApiAccess'
      if (!this.can(key)) return
      this.apiForm = {
        open: true,
        id: row ? row.id : '',
        value: row ? { appName: row.appName, tenantName: row.tenantName, dataScopeLabel: row.dataScopeLabel, ipWhitelist: row.ipWhitelist, validUntil: row.validUntil } : { appName: '', tenantName: '', dataScopeLabel: '', ipWhitelist: '', validUntil: '' },
        errors: {},
        submitting: false
      }
    },
    async submitApiForm() {
      const errors = FormFields.validateRequired(this.apiFormFields, this.apiForm.value)
      this.apiForm.errors = errors
      if (Object.keys(errors).length) return
      this.apiForm.submitting = true
      const res = await platformApi.saveApiAccess({ id: this.apiForm.id || undefined, ...this.apiForm.value })
      this.apiForm.submitting = false
      if (res.code === 0) {
        toast.success((this.apiForm.id ? '配置已更新' : '应用已创建，Secret 已一次性下发') + '，已留痕')
        this.apiForm.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openApiDetail(row) {
      this.apiDetail = { open: true, row }
    },
    askResetSecret(row) {
      if (!this.can('resetApiSecret')) return
      this.actionRow = row
      this.confirmReset = true
    },
    async doResetSecret({ reason }) {
      this.confirmSubmitting = true
      const res = await platformApi.resetApiSecret(this.actionRow.id, { reason })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success(res.data.notice)
        this.confirmReset = false
      } else {
        toast.error(res.message)
      }
    },
    askDisableApi(row) {
      if (!this.can('disableApiAccess')) return
      this.actionRow = row
      this.confirmDisableApi = true
    },
    async doDisableApi({ reason }) {
      this.confirmSubmitting = true
      const res = await platformApi.setApiAccessStatus(this.actionRow.id, { action: 'DISABLE', reason })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('API 访问已停用（调用即时 403），原因已留痕')
        this.confirmDisableApi = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doEnableApi(row) {
      if (!this.can('disableApiAccess')) return
      const res = await platformApi.setApiAccessStatus(row.id, { action: 'ENABLE' })
      if (res.code === 0) {
        toast.success('API 访问已恢复，已留痕')
        this.load()
      }
    },
    async doExportLogs() {
      if (!this.can('exportApiLogs')) return
      const res = await platformApi.exportApiLogs()
      if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（AppKey 脱敏 + 水印），已留痕')
    },
    openWebhookEdit(row) {
      const key = row ? 'editWebhook' : 'createWebhook'
      if (!this.can(key)) return
      this.whForm = {
        open: true,
        id: row ? row.id : '',
        value: row ? { name: row.name, tenantName: row.tenantName, url: row.urlMasked, retryPolicy: row.retryPolicy } : { name: '', tenantName: '', url: '', retryPolicy: '指数退避 · 最多 5 次' },
        errors: {},
        submitting: false
      }
    },
    async submitWebhookForm() {
      const errors = FormFields.validateRequired(this.whFormFields, this.whForm.value)
      this.whForm.errors = errors
      if (Object.keys(errors).length) return
      this.whForm.submitting = true
      const res = await platformApi.saveWebhook({ id: this.whForm.id || undefined, ...this.whForm.value })
      this.whForm.submitting = false
      if (res.code === 0) {
        toast.success((this.whForm.id ? '订阅已更新' : '订阅已创建，签名密钥一次性下发') + '，已留痕')
        this.whForm.open = false
        this.switchWebhook()
      } else {
        toast.error(res.message)
      }
    },
    askDisableWebhook(row) {
      if (!this.can('disableWebhook')) return
      this.actionRow = row
      this.confirmDisableWebhook = true
    },
    async doDisableWebhook({ reason }) {
      this.confirmSubmitting = true
      const res = await platformApi.setWebhookStatus(this.actionRow.id, { action: 'DISABLE', reason })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('Webhook 已停用，原因已留痕')
        this.confirmDisableWebhook = false
        this.switchWebhook()
      } else {
        toast.error(res.message)
      }
    },
    async doEnableWebhook(row) {
      if (!this.can('disableWebhook')) return
      const res = await platformApi.setWebhookStatus(row.id, { action: 'ENABLE' })
      if (res.code === 0) {
        toast.success('Webhook 已恢复投递，已留痕')
        this.switchWebhook()
      }
    },
    async doRedeliver(row) {
      if (!this.can('redeliverWebhook')) return
      const res = await platformApi.redeliverWebhook(row.id)
      if (res.code === 0) {
        toast.success('失败事件已重推成功，已留痕')
        this.switchWebhook()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [listRes, logRes] = await Promise.all([
        platformApi.getApiAccessList({ page: this.pagination.page, pageSize: this.pagination.pageSize }),
        platformApi.getApiCallLogs()
      ])
      if (listRes.code === 0) {
        this.rows = listRes.data.list
        this.pagination.total = listRes.data.total
      } else {
        this.error = listRes.message
      }
      if (logRes.code === 0) this.callLogs = logRes.data
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-danger {
  color: var(--danger-600);
}
.aa-fail {
  color: var(--danger-600);
}
.aa-event {
  display: inline-block;
  font-size: 10px;
  color: var(--primary-600);
  background: var(--primary-50);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-1);
  margin: 1px var(--space-1) 1px 0;
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
