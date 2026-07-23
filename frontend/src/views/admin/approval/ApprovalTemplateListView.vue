<template>
  <ModulePageShell
    title="审批模板"
    subtitle="按业务类型配置节点流转与办理时限，作废为逻辑作废并留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar v-if="canView" :actions="toolbarActions" hint="模板变更全部留痕" @action="onToolbar" />
    </template>

    <AppGlobalState
      v-if="!canView"
      state="forbidden"
      title="当前身份无权管理审批模板"
      :description="viewReason + '；请联系学校管理员为你开通审批模板权限，或切换到具备权限的真实身份'"
      @back="$router.push('/admin/approval')"
      @contact="onContact"
    />
    <div v-else class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="没有符合条件的审批模板"
        description="可调整筛选条件，或新增模板以启用对应业务的审批流转"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.id }}</div>
        </template>
        <template #cell-nodes="{ row }">{{ row.nodes.length }} 个节点</template>
        <template #cell-status="{ row }">
          <StatusTag
            :type="row.status === 'ENABLED' ? 'success' : 'default'"
            :label="row.statusLabel"
            dot
          />
        </template>
        <template #cell-updated="{ row }">
          <div class="mp-cell-main">{{ row.updatedBy }}</div>
          <div class="mp-cell-sub">{{ row.updatedAt }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openView(row)">查看</button>
          <button
            class="mp-link"
            style="margin-left: var(--space-2)"
            :class="{ 'is-disabled': !can('editTemplate') || row.status === 'VOIDED' }"
            :title="editDisabledTip(row)"
            @click="openEdit(row)"
          >
            编辑
          </button>
          <button
            class="mp-link"
            style="margin-left: var(--space-2)"
            :class="{ 'is-disabled': !can('voidTemplate') || row.status === 'VOIDED' }"
            :title="voidDisabledTip(row)"
            @click="openVoid(row)"
          >
            作废
          </button>
          <button
            class="mp-link"
            style="margin-left: var(--space-2)"
            :class="{ 'is-disabled': !can('exportTemplates') }"
            :title="reason('exportTemplates')"
            @click="openExport(row)"
          >
            导出
          </button>
        </template>
      </DataTable>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">最近审计留痕</span>
          <span class="mp-note">模板新增、更新、作废与导出全部留痕</span>
        </div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead>
              <tr><th>操作人</th><th>时间</th><th>动作</th><th>对象</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in audits" :key="a.id">
                <td class="is-who">{{ a.who }} · {{ a.roleName }}</td>
                <td>{{ a.time }}</td>
                <td>{{ a.action }}</td>
                <td>{{ a.target }}</td>
                <td>{{ a.detail }}</td>
              </tr>
              <tr v-if="!audits.length">
                <td colspan="5" class="mp-note">暂无审计记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <AppDrawer v-model:visible="viewDrawer" :title="viewTarget ? viewTarget.name : '模板详情'">
      <template v-if="viewTarget">
        <div class="mp-kv"><span class="mp-kv__k">适用业务</span><span class="mp-kv__v">{{ viewTarget.bizTypeLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">当前版本</span><span class="mp-kv__v">{{ viewTarget.version }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v">{{ viewTarget.statusLabel }}</span></div>
        <div class="mp-kv">
          <span class="mp-kv__k">最近更新</span>
          <span class="mp-kv__v">{{ viewTarget.updatedBy }} · {{ viewTarget.updatedAt }}</span>
        </div>
        <p v-if="viewTarget.voidReason" class="mp-note" style="margin: var(--space-2) 0 0">
          作废原因：{{ viewTarget.voidReason }}
        </p>
        <div class="mp-card__head" style="padding: var(--space-4) 0 var(--space-2); border-bottom: none">
          <span class="mp-card__title">节点流转</span>
        </div>
        <ul class="mp-timeline">
          <li
            v-for="(n, i) in viewTarget.nodes"
            :key="i"
            class="mp-timeline__item"
            :class="i === 0 ? 'is-success' : 'is-default'"
          >
            <div class="mp-timeline__title">{{ i + 1 }}. {{ n.name }}</div>
            <div class="mp-timeline__desc">办理角色：{{ n.roleLabel }} · 办理时限 {{ n.sla }} 小时</div>
          </li>
        </ul>
      </template>
      <template #footer>
        <AppButton variant="ghost" @click="viewDrawer = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="formDrawer" :title="formMode === 'create' ? '新增审批模板' : '编辑审批模板'">
      <label class="mp-note" style="display: block; margin-bottom: var(--space-1)">模板名称 *</label>
      <input v-model="form.name" type="text" class="tp-input" placeholder="例如：某业务审批流" />
      <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">适用业务 *</label>
      <select v-model="form.bizType" class="tp-input">
        <option value="">请选择业务类型</option>
        <option v-for="b in ctx.filterOptions.bizTypes" :key="b.value" :value="b.value">{{ b.label }}</option>
      </select>

      <div style="display: flex; align-items: center; justify-content: space-between; margin: var(--space-4) 0 var(--space-2)">
        <span class="mp-card__title">审批节点（按顺序流转）*</span>
        <button class="mp-link" @click="addNode">＋ 添加节点</button>
      </div>
      <div v-for="(n, i) in form.nodes" :key="i" class="tp-node">
        <span class="tp-node__index">{{ i + 1 }}</span>
        <input v-model="n.name" type="text" class="tp-input tp-node__name" placeholder="节点名称" />
        <select v-model="n.role" class="tp-input tp-node__role">
          <option value="">办理角色</option>
          <option v-for="r in ctx.filterOptions.templateNodeRoles" :key="r.value" :value="r.value">
            {{ r.label }}
          </option>
        </select>
        <input v-model="n.sla" type="number" min="1" class="tp-input tp-node__sla" placeholder="时限(h)" />
        <button
          class="mp-link"
          :class="{ 'is-disabled': form.nodes.length <= 1 }"
          title="至少保留 1 个节点"
          @click="removeNode(i)"
        >
          删除
        </button>
      </div>
      <p v-if="formError" class="mp-form-err">{{ formError }}</p>
      <p class="mp-note" style="margin-top: var(--space-3)">
        保存后版本号自动递增，历史在办单据仍按原版本流转，模板变更写入审计留痕。
      </p>
      <template #footer>
        <AppButton variant="ghost" @click="formDrawer = false">取消</AppButton>
        <AppButton variant="primary" :loading="submitting" @click="submitForm">
          {{ formMode === 'create' ? '确认新增' : '确认保存' }}
        </AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="voidDialog"
      title="作废模板确认"
      :message="voidTarget ? '作废后「' + voidTarget.name + '」不再用于新申请，历史单据保留可追溯，此操作不可恢复。' : ''"
      type="danger"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请写明作废原因（不少于 5 个字），将写入审计留痕"
      :submitting="submitting"
      @confirm="doVoid"
    />
    <AppConfirmDialog
      v-model:visible="exportDialog"
      title="导出审批模板"
      :message="(exportTarget ? '将导出「' + exportTarget.name + '」的节点配置，' : '') + '文件默认加水印，导出动作写入审计日志。'"
      type="primary"
      confirm-text="确认导出"
      :submitting="submitting"
      @confirm="doExport"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 审批模板（/admin/approval/templates）：模板列表 + 节点行编辑 + 查看/编辑/作废/导出闭环。
 * 仅具备 viewTemplates 权限的角色可见列表（其余角色整页 forbidden 演示无权限态）；
 * 管理动作按 permissionActions 置灰并提示原因。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog, AppGlobalState } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { approvalApi } from '@/modules/approval/api/approval.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ bizType: '', status: '', keyword: '' })
const EMPTY_NODE = () => ({ name: '', role: '', sla: 24 })

export default {
  name: 'ApprovalTemplateListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppConfirmDialog,
    AppGlobalState,
    AppButton,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      audits: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      viewDrawer: false,
      viewTarget: null,
      formDrawer: false,
      formMode: 'create',
      form: { id: '', name: '', bizType: '', nodes: [EMPTY_NODE()] },
      formError: '',
      voidDialog: false,
      voidTarget: null,
      exportDialog: false,
      exportTarget: null,
      submitting: false,
      columns: [
        { key: 'name', title: '模板名称' },
        { key: 'bizTypeLabel', title: '适用业务' },
        { key: 'nodes', title: '节点数' },
        { key: 'version', title: '版本' },
        { key: 'status', title: '状态' },
        { key: 'updated', title: '更新人 / 时间' },
        { key: 'actions', title: '操作', width: '210px' }
      ]
    }
  },
  computed: {
    canView() {
      return this.can('viewTemplates')
    },
    viewReason() {
      return this.reason('viewTemplates') || '不在授权范围内'
    },
    filterFields() {
      const o = this.ctx.filterOptions
      return [
        { key: 'bizType', label: '适用业务', type: 'select', options: o.bizTypes },
        { key: 'status', label: '模板状态', type: 'select', options: o.templateStatuses },
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '模板名称' }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'createTemplate', label: '＋ 新增模板', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    if (this.canView) {
      this.load()
      this.loadAudits()
    }
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
    editDisabledTip(row) {
      if (!this.can('editTemplate')) return this.reason('editTemplate')
      return row.status === 'VOIDED' ? '已作废模板不可编辑' : ''
    },
    voidDisabledTip(row) {
      if (!this.can('voidTemplate')) return this.reason('voidTemplate')
      return row.status === 'VOIDED' ? '该模板已是作废状态' : ''
    },
    onContact() {
      toast.info('已提交权限申请示意：请联系拥有模板管理权限的角色开通')
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
      this.pagination.page = 1
      this.load()
    },
    onToolbar(key) {
      if (key === 'createTemplate') this.openCreate()
    },
    openView(row) {
      this.viewTarget = row
      this.viewDrawer = true
    },
    openCreate() {
      this.formMode = 'create'
      this.form = { id: '', name: '', bizType: '', nodes: [EMPTY_NODE()] }
      this.formError = ''
      this.formDrawer = true
    },
    openEdit(row) {
      if (!this.can('editTemplate') || row.status === 'VOIDED') return
      this.formMode = 'edit'
      this.form = {
        id: row.id,
        name: row.name,
        bizType: row.bizType,
        nodes: row.nodes.map((n) => ({ name: n.name, role: n.role, sla: n.sla }))
      }
      this.formError = ''
      this.formDrawer = true
    },
    openVoid(row) {
      if (!this.can('voidTemplate') || row.status === 'VOIDED') return
      this.voidTarget = row
      this.voidDialog = true
    },
    openExport(row) {
      if (!this.can('exportTemplates')) return
      this.exportTarget = row
      this.exportDialog = true
    },
    addNode() {
      this.form.nodes.push(EMPTY_NODE())
    },
    removeNode(i) {
      if (this.form.nodes.length <= 1) return
      this.form.nodes.splice(i, 1)
    },
    async submitForm() {
      this.formError = ''
      this.submitting = true
      const payload = { name: this.form.name, bizType: this.form.bizType, nodes: this.form.nodes }
      const res =
        this.formMode === 'create'
          ? await approvalApi.createTemplate(payload)
          : await approvalApi.updateTemplate(this.form.id, payload)
      this.submitting = false
      if (res.code === 0) {
        this.formDrawer = false
        toast.success(
          this.formMode === 'create'
            ? '模板已新增（' + res.data.version + '）并写入审计留痕'
            : '模板已保存，版本升级至 ' + res.data.version + '，已写入审计留痕'
        )
        this.load()
        this.loadAudits()
      } else {
        this.formError = res.message
      }
    },
    async doVoid({ reason }) {
      this.submitting = true
      const res = await approvalApi.voidTemplate(this.voidTarget.id, { reason })
      this.submitting = false
      this.voidDialog = false
      if (res.code === 0) {
        toast.success('模板已作废：历史单据保留可追溯，作废原因已写入审计留痕')
        this.load()
        this.loadAudits()
      } else {
        toast.error(res.message)
      }
    },
    async doExport() {
      this.submitting = true
      const res = await approvalApi.exportRecords({
        scope: 'TEMPLATE',
        purpose: this.exportTarget ? '模板配置备份：' + this.exportTarget.name : '模板配置备份'
      })
      this.submitting = false
      this.exportDialog = false
      if (res.code === 0) {
        toast.success('导出任务已创建（' + res.data.auditId + '）：文件含水印，已写入审计日志')
        this.loadAudits()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await approvalApi.getTemplates({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async loadAudits() {
      const res = await approvalApi.getAuditLogs()
      if (res.code === 0) this.audits = res.data.slice(0, 6)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.tp-input {
  width: 100%;
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
  box-sizing: border-box;
  transition: border-color var(--motion-fast) var(--ease-standard);
}
.tp-input:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.tp-node {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.tp-node__index {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: var(--font-size-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tp-node__name {
  flex: 1.4;
}
.tp-node__role {
  flex: 1;
}
.tp-node__sla {
  width: 76px;
  flex-shrink: 0;
}
</style>
