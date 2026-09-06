<template>
  <ModulePageShell
    title="数据范围管理"
    subtitle="数据范围独立于角色配置：全校 / 学院 / 专业 / 班级 / 本人 / 指导关系 / 企业授权 / 临时授权"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <!--
        SYS-08 显式 DENY。上面的范围规则表达"能看哪些"，这里表达"当前角色不可访问哪些"。
        把"某节点不可见"写成"少给一个 ALLOW"是不可靠的：任何人给这个角色配个更大的
        范围就击穿了。DENY 判定永远最先命中，且不可被任何 ALLOW 覆盖。
      -->
      <section class="mp-card ds-deny">
        <header class="mp-card__head">
          <span class="mp-card__title">显式禁止（DENY）</span>
          <span>
            <span class="mp-note">DENY 优先于一切 ALLOW，含继承</span>
            <button class="mp-link" @click="denyPanel.open = !denyPanel.open">
              {{ denyPanel.open ? '收起' : '展开' }}
            </button>
          </span>
        </header>
        <div v-if="denyPanel.open" class="mp-card__body" style="padding-top: 0">
          <LoadingState v-if="denyPanel.loading" />
          <ErrorState v-else-if="denyPanel.error" :description="denyPanel.error" @retry="loadDenyPolicies" />
          <table v-else-if="denyPanel.items.length" class="mp-audit">
            <thead>
              <tr>
                <th style="width: 170px">角色</th>
                <th style="width: 90px">效果</th>
                <th style="width: 190px">目标</th>
                <th style="width: 90px">向下继承</th>
                <th style="width: 165px">生效期间</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in denyPanel.items" :key="p.policyId">
                <td class="is-who">{{ p.roleCode }}</td>
                <td>
                  <StatusTag :type="p.effect === 'DENY' ? 'danger' : 'success'" :label="p.effect" />
                </td>
                <td>{{ p.targetType }}:{{ p.targetId }}</td>
                <td>{{ p.includeChildren ? '是' : '否' }}</td>
                <td class="mp-cell-sub">
                  {{ fmtTime(p.effectiveAt) }} ~ {{ p.expiresAt ? fmtTime(p.expiresAt) : '长期' }}
                </td>
                <td class="mp-cell-sub">{{ p.reason }}</td>
              </tr>
            </tbody>
          </table>
          <EmptyState
            v-if="!denyPanel.loading && !denyPanel.error && !denyPanel.items.length"
            title="尚未配置任何显式策略"
            description="显式策略由服务端维护与判断，不能用扩大默认范围替代策略复核。"
          />
          <p class="mp-note" style="margin-top: var(--space-2)">
            判定顺序：DENY → 继承 DENY → 敏感专项 → 业务关系 → 直接 ALLOW → 继承 ALLOW → 默认拒绝
          </p>
        </div>
      </section>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="load" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的规则" description="可调整筛选条件或新增数据范围规则" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-rule="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.scopeCode }}</div>
        </template>
        <template #cell-scopeLabel="{ row }">
          <StatusTag type="info" :label="row.scopeLabel" />
        </template>
        <template #cell-appliedRoles="{ row }">
          <span class="mp-cell-sub">{{ row.appliedRoles.join('、') || '未引用' }}</span>
        </template>
        <template #cell-affectedUsers="{ row }">
          <button class="mp-link" :class="{ 'is-disabled': !can('viewScopeAffected') }" :title="reason('viewScopeAffected')" @click="openAffected(row)">
            {{ row.affectedUsers == null ? '未取得' : row.affectedUsers + ' 人（历史匹配口径）' }}
          </button>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :class="{ 'is-disabled': !can('editScopeRule') }" :title="reason('editScopeRule')" @click="openEdit(row)">编辑</button>
          <button
            v-if="row.status === 'ENABLED'"
            class="mp-link ds-danger"
            :class="{ 'is-disabled': !can('deprecateScopeRule') }"
            :title="reason('deprecateScopeRule')"
            @click="askDeprecate(row)"
          >作废</button>
          <span v-else class="mp-note">已作废</span>
        </template>
      </DataTable>

      <p class="mp-note">
        引用角色与人数来自当前历史匹配口径，不代表所有结构化权限的完整影响。作废前先核对角色引用，由后端再次校验。
      </p>
    </div>

    <!-- 新增 / 编辑规则 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑数据范围规则' : '新增数据范围规则'" mode="modal" size="medium">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存规则</AppButton>
      </template>
    </AppDrawer>

    <!-- 影响用户 -->
    <AppDrawer v-model:visible="affected.open" :title="'影响用户 · ' + affected.name" mode="modal" size="large">
      <LoadingState v-if="affected.loading" />
      <ErrorState v-else-if="affected.error" :description="affected.error" @retry="openAffected({ id: affected.id, name: affected.name })" />
      <EmptyState v-else-if="!affected.list.length" title="当前历史匹配口径未返回记录" description="这是受限预览，不能据此证明所有结构化权限都没有影响。" />
      <template v-else>
        <p class="mp-note">受限预览：最多 200 条用户与角色关联记录，可能包含同一用户的多个角色，不代表完整人数。</p>
        <div v-for="(u, index) in affected.list" :key="`${u.id}:${u.roleName}:${index}`" class="mp-kv">
          <span class="mp-kv__k">{{ u.name }} · {{ u.roleName || '—' }}</span>
          <span class="mp-kv__v">{{ u.orgName || u.userNo || '—' }}</span>
        </div>
        <p class="mp-note" style="margin-top: var(--space-2)">仅展示姓名与组织，联系方式等敏感字段不在此页展示。</p>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDeprecate"
      type="danger"
      :title="'作废规则「' + (deprecateRow ? deprecateRow.name : '') + '」？'"
      message="作废为逻辑删除：历史引用记录保留可追溯；作废后该规则不可再被角色引用。"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      :submitting="deprecateSubmitting"
      @confirm="doDeprecate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 数据范围管理（/admin/system/scopes）：
 * 新增 / 编辑 / 作废（逻辑删除+原因留痕）/ 查看影响用户 / 导出规则清单。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'
import { contextFingerprint, createRequestFence } from '../utils/workspaceContract'

export default {
  name: 'SystemDataScopeView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, FormFields
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      fence: null,
      loading: true,
      error: '',
      rows: [],
      // SYS-08 显式 DENY 策略（默认收起，不干扰既有范围规则管理）
      denyPanel: { open: false, items: [], loading: false, error: '' },
      filters: { keyword: '', status: '' },
      columns: [
        { key: 'rule', title: '规则' },
        { key: 'scopeLabel', title: '范围类型' },
        { key: 'appliedRoles', title: '引用角色' },
        { key: 'affectedUsers', title: '影响用户' },
        { key: 'remark', title: '说明' },
        { key: 'status', title: '状态' },
        { key: 'updatedAt', title: '最近更新' },
        { key: 'actions', title: '操作', width: '140px' }
      ],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      affected: { open: false, loading: false, id: '', name: '', list: [], error: '' },
      confirmDeprecate: false,
      deprecateRow: null,
      deprecateSubmitting: false
    }
  },
  computed: {
    contextKey() { return contextFingerprint(this.ctx) },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '规则名称' },
        { key: 'status', label: '状态', type: 'select', options: this.ctx.statusOptions.ruleStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createScopeRule', label: '＋ 新增规则', variant: 'primary' },
        { key: 'exportScopeRules', label: '⇩ 导出规则清单' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '规则名称', required: true, placeholder: '如：本学院范围' },
        { key: 'scopeCode', label: '范围类型', type: 'select', required: true, options: this.ctx.statusOptions.scopeTypes },
        { key: 'remark', label: '规则说明', type: 'textarea', full: true, placeholder: '计算口径与边界，如「按任职学院自动计算，跨院不可见」' }
      ]
    }
  },
  created() { this.fence = createRequestFence(); this.load() },
  beforeUnmount() { this.fence.invalidate() },
  watch: {
    'affected.open'(open) { if (!open) this.fence.start('affected') },
    contextKey() { this.fence.invalidate(); this.affected = { open: false, loading: false, id: '', name: '', list: [], error: '' }; this.rows = []; this.denyPanel = { open: false, items: [], loading: false, error: '' }; this.form = { open: false, id: '', value: {}, errors: {}, submitting: false }; this.confirmDeprecate = false; this.deprecateRow = null; this.deprecateSubmitting = false; this.load() }
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
    reset() {
      this.filters = { keyword: '', status: '' }
      this.load()
    },
    async onToolbar(key) {
      if (key === 'createScopeRule') this.openEdit(null)
      if (key === 'exportScopeRules') {
        const res = await systemApi.exportScopeRules()
        if (res.code === 0) toast.success('数据范围清单已下载：' + res.data.fileName + '（含水印），已留痕')
        else toast.error(res.message)
      }
    },
    openEdit(row) {
      const key = row ? 'editScopeRule' : 'createScopeRule'
      if (!this.can(key)) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row ? { name: row.name, scopeCode: row.scopeCode, remark: row.remark } : { name: '', scopeCode: '', remark: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      if (this.form.submitting || !this.form.open || !this.can(this.form.id ? 'editScopeRule' : 'createScopeRule')) return
      const current = this.fence.start('form-write')
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.saveScopeRule({ id: this.form.id || undefined, ...this.form.value })
      if (!current()) return
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('规则已保存并留痕')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openAffected(row) {
      if (!this.can('viewScopeAffected')) return
      const current = this.fence.start('affected')
      this.affected = { open: true, loading: true, id: row.id, name: row.name, list: [], error: '' }
      try {
        const res = await systemApi.getScopeAffectedUsers(row.id)
        if (!current()) return
        if (res.code !== 0 || !Array.isArray(res.data)) throw new Error(res.message || '影响用户数据未取得')
        this.affected.list = res.data
      } catch (error) { if (current()) this.affected.error = error.message || '影响用户读取失败，人数未取得' }
      finally { if (current()) this.affected.loading = false }
    },
    askDeprecate(row) {
      if (!this.can('deprecateScopeRule')) return
      this.deprecateRow = row
      this.confirmDeprecate = true
    },
    async doDeprecate({ reason }) {
      if (this.deprecateSubmitting || !this.deprecateRow || !this.can('deprecateScopeRule')) return
      const current = this.fence.start('status-write')
      this.deprecateSubmitting = true
      const res = await systemApi.deprecateScopeRule(this.deprecateRow.id, { reason })
      if (!current()) return
      this.deprecateSubmitting = false
      if (res.code === 0) {
        toast.success('规则已作废（逻辑删除），原因已留痕')
        this.confirmDeprecate = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      const current = this.fence.start('rules')
      this.loading = true
      this.error = ''
      const res = await systemApi.getScopeRules(this.filters)
      if (!current()) return
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
      this.loadDenyPolicies()
    },

    fmtTime(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },

    /** SYS-08 显式策略。加载失败不阻断既有范围规则列表。 */
    async loadDenyPolicies() {
      const current = this.fence.start('policies')
      this.denyPanel.loading = true; this.denyPanel.error = ''
      try {
        const res = await systemApi.getScopePolicies()
        if (!current()) return
        if (res.code !== 0 || !Array.isArray(res.data?.items)) throw new Error(res.message || '显式策略结果不完整')
        this.denyPanel.items = res.data.items
      } catch (error) { if (current()) this.denyPanel.error = error.message || '显式策略未取得' }
      finally { if (current()) this.denyPanel.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ds-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
/* SYS-08 显式 DENY */
.ds-deny {
  border-left: 3px solid var(--danger-600);
}
</style>
