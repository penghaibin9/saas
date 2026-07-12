<template>
  <ModulePageShell
    title="组织结构管理"
    subtitle="院系 / 专业 / 班级 / 职能部门 · 数据范围计算的组织基座"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'tree' }" @click="tab = 'tree'">组织树</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'positions' }" @click="tab = 'positions'">岗位管理</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else-if="tab === 'tree'">
        <EmptyState v-if="!tree.length" title="暂无组织数据" description="可通过「批量导入」初始化院系 / 专业 / 班级结构" />
        <section v-else class="mp-card">
          <div class="mp-card__body" style="padding-top: var(--space-2)">
            <table class="og-table">
              <thead>
                <tr><th>组织</th><th style="width: 110px">类型</th><th style="width: 110px">编码</th><th style="width: 90px">成员数</th><th style="width: 210px">操作</th></tr>
              </thead>
              <tbody>
                <template v-for="node in flatTree" :key="node.id">
                  <tr>
                    <td :style="{ paddingLeft: 12 + node.depth * 24 + 'px' }">
                      <span v-if="node.depth" class="og-branch">├</span>
                      <b v-if="node.depth === 0">{{ node.name }}</b>
                      <span v-else>{{ node.name }}</span>
                    </td>
                    <td><StatusTag :type="node.depth === 0 ? 'info' : node.type === 'CLASS' ? 'processing' : 'default'" :label="node.typeLabel" /></td>
                    <td class="mp-cell-sub">{{ node.code }}</td>
                    <td class="mp-cell-sub">{{ node.memberCount }}</td>
                    <td>
                      <button class="mp-link" :class="{ 'is-disabled': !can('createOrg') }" :title="reason('createOrg')" @click="openEdit(null, node)">＋ 下级</button>
                      <button class="mp-link" :class="{ 'is-disabled': !can('editOrg') }" :title="reason('editOrg')" @click="openEdit(node, null)">编辑</button>
                      <button class="mp-link og-danger" :class="{ 'is-disabled': !can('deprecateOrg') }" :title="reason('deprecateOrg')" @click="askDeprecate(node)">作废</button>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </section>
        <p class="mp-note">组织节点作废为逻辑删除：历史归属关系保留；如节点下仍有在册成员，需先转移成员再作废。</p>
      </template>

      <template v-else>
        <EmptyState v-if="!positions.length" title="暂无岗位" description="岗位用于批量绑定角色与数据范围" />
        <DataTable v-else :columns="posColumns" :rows="positions" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
          </template>
        </DataTable>
        <p class="mp-note">岗位与账号的绑定在「用户账号管理」中维护；岗位仅作为角色 / 数据范围的批量配置入口。</p>
      </template>
    </div>

    <!-- 新增 / 编辑组织节点 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑组织节点' : '新增下级组织'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p v-if="form.parentName" class="mp-note" style="margin-top: var(--space-2)">上级组织：{{ form.parentName }}</p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDeprecate"
      type="danger"
      :title="'作废组织「' + (deprecateRow ? deprecateRow.name : '') + '」？'"
      :message="deprecateRow && deprecateRow.memberCount > 0
        ? '该组织下仍有 ' + deprecateRow.memberCount + ' 名成员，作废前需先完成转移；此处仅演示确认流程。'
        : '作废为逻辑删除，历史归属关系保留可追溯。'"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      :submitting="deprecateSubmitting"
      @confirm="doDeprecate"
    />

    <ImportDialog
      v-model:visible="importOpen"
      :template="ctx.importTemplates.org"
      :run-validate="() => api.importOrg()"
      :run-import="() => api.importOrg({ confirm: true })"
      @done="load"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 组织结构管理（/admin/system/org）：
 * 组织树（学院/专业/班级/部门）增改 / 作废留痕 / 导入导出；岗位列表。
 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import ImportDialog from '@/modules/system/components/ImportDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const ORG_TYPES = [
  { value: 'COLLEGE', label: '学院' },
  { value: 'MAJOR', label: '专业' },
  { value: 'CLASS', label: '班级' },
  { value: 'DEPT', label: '部门' }
]

export default {
  name: 'SystemOrgView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppConfirmDialog, FormFields, ImportDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: systemApi,
      tab: 'tree',
      loading: true,
      error: '',
      tree: [],
      positions: [],
      posColumns: [
        { key: 'name', title: '岗位' },
        { key: 'orgName', title: '所属组织' },
        { key: 'memberCount', title: '成员数' },
        { key: 'remark', title: '说明' },
        { key: 'status', title: '状态' }
      ],
      form: { open: false, id: '', parentName: '', value: {}, errors: {}, submitting: false },
      confirmDeprecate: false,
      deprecateRow: null,
      deprecateSubmitting: false,
      importOpen: false
    }
  },
  computed: {
    flatTree() {
      const out = []
      const walk = (nodes, depth) => {
        nodes.forEach((n) => {
          out.push({ ...n, depth })
          if (n.children && n.children.length) walk(n.children, depth + 1)
        })
      }
      walk(this.tree, 0)
      return out
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createOrg', label: '＋ 新增学院/部门', variant: 'primary' },
        { key: 'importOrg', label: '⇪ 批量导入' },
        { key: 'exportOrg', label: '⇩ 导出组织结构' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '组织名称', required: true },
        { key: 'code', label: '组织编码', required: true, disabled: !!this.form.id, lockNote: this.form.id ? '（不可修改）' : '' },
        { key: 'type', label: '组织类型', type: 'select', required: true, options: ORG_TYPES }
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
    async onToolbar(key) {
      if (key === 'createOrg') this.openEdit(null, null)
      if (key === 'importOrg') this.importOpen = true
      if (key === 'exportOrg') {
        const res = await systemApi.exportOrg()
        if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（含水印），已留痕')
      }
    },
    openEdit(node, parent) {
      const key = node ? 'editOrg' : 'createOrg'
      if (!this.can(key)) return
      this.form = {
        open: true,
        id: node ? node.id : '',
        parentName: parent ? parent.name : node ? '' : '（顶级）',
        value: node ? { name: node.name, code: node.code, type: node.type } : { name: '', code: '', type: parent ? (parent.type === 'COLLEGE' ? 'MAJOR' : parent.type === 'MAJOR' ? 'CLASS' : 'DEPT') : 'COLLEGE' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const typeLabel = (ORG_TYPES.find((t) => t.value === this.form.value.type) || {}).label
      const res = await systemApi.saveOrgNode({ id: this.form.id || undefined, ...this.form.value, typeLabel })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('组织节点已保存并留痕（演示环境不改变树结构展示）')
        this.form.open = false
      } else {
        toast.error(res.message)
      }
    },
    askDeprecate(node) {
      if (!this.can('deprecateOrg')) return
      this.deprecateRow = node
      this.confirmDeprecate = true
    },
    async doDeprecate({ reason }) {
      this.deprecateSubmitting = true
      const res = await systemApi.deprecateOrgNode(this.deprecateRow.id, { name: this.deprecateRow.name, reason })
      this.deprecateSubmitting = false
      if (res.code === 0) {
        toast.success('组织节点已作废（逻辑删除），原因已留痕')
        this.confirmDeprecate = false
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [treeRes, posRes] = await Promise.all([systemApi.getDepartmentTree(), systemApi.getPositions()])
      if (treeRes.code === 0) this.tree = treeRes.data
      else this.error = treeRes.message
      if (posRes.code === 0) this.positions = posRes.data
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.og-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.og-table th {
  text-align: left;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-base);
}
.og-table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
}
.og-branch {
  color: var(--text-tertiary);
  margin-right: var(--space-1);
}
.og-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
