<template>
  <ModulePageShell
    title="菜单权限管理"
    subtitle="菜单可见性 / 按钮权限点 / 按角色预览 · 菜单结构变更仅系统管理员可操作"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar">
        <template #right>
          <label class="mn-preview">
            按角色预览
            <select v-model="previewRole" class="mn-select" @change="loadPreview">
              <option value="">关闭预览</option>
              <option v-for="r in ctx.filterOptions.roles" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </label>
        </template>
      </ModuleToolbar>
    </template>

    <div class="mp-stack">
      <div v-if="previewRole" class="mn-notice">
        正在预览「{{ previewRoleLabel }}」可见菜单：不可见菜单以灰显标注，仅供核对，不影响实际配置。
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!tree.length" title="暂无菜单配置" description="请联系系统管理员初始化菜单结构" />
      <section v-else class="mp-card">
        <div class="mp-card__body" style="padding-top: var(--space-2)">
          <table class="mn-table">
            <thead>
              <tr><th>菜单</th><th>路径</th><th>按钮权限点</th><th style="width: 90px">状态</th><th style="width: 200px">操作</th></tr>
            </thead>
            <tbody>
              <template v-for="mod in tree" :key="mod.id">
                <tr class="mn-mod" :class="{ 'is-dim': dimmed(mod.code) }">
                  <td><b>{{ mod.icon }} {{ mod.name }}</b><span class="mp-cell-sub">模块 · {{ mod.moduleCode }}</span></td>
                  <td class="mp-cell-sub">{{ mod.path }}</td>
                  <td class="mp-cell-sub">—</td>
                  <td><StatusTag :type="mod.status === 'ENABLED' ? 'success' : 'default'" :label="mod.statusLabel" dot /></td>
                  <td>
                    <button class="mp-link" :class="{ 'is-disabled': !can('editMenu') }" :title="reason('editMenu')" @click="openEdit(mod)">编辑</button>
                    <button
                      v-if="mod.status === 'ENABLED'"
                      class="mp-link mn-danger"
                      :class="{ 'is-disabled': !can('disableMenu') }"
                      :title="reason('disableMenu')"
                      @click="askDisable(mod)"
                    >停用</button>
                    <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableMenu') }" :title="reason('disableMenu')" @click="doEnable(mod)">启用</button>
                  </td>
                </tr>
                <tr v-for="m in mod.children" :key="m.id" :class="{ 'is-dim': dimmed(m.code) }">
                  <td class="mn-sub">├ {{ m.name }}</td>
                  <td class="mp-cell-sub">{{ m.path }}</td>
                  <td>
                    <template v-if="m.buttons.length">
                      <code v-for="b in m.buttons" :key="b.code" class="mn-btncode" :title="b.name">{{ b.code }}</code>
                      <button class="mp-link" :class="{ 'is-disabled': !can('configMenuButtons') }" :title="reason('configMenuButtons')" @click="openButtons(m)">配置</button>
                    </template>
                    <button v-else class="mp-link" :class="{ 'is-disabled': !can('configMenuButtons') }" :title="reason('configMenuButtons')" @click="openButtons(m)">＋ 配置按钮</button>
                  </td>
                  <td><StatusTag :type="m.status === 'ENABLED' ? 'success' : 'default'" :label="m.statusLabel" dot /></td>
                  <td>
                    <button class="mp-link" :class="{ 'is-disabled': !can('editMenu') }" :title="reason('editMenu')" @click="openEdit(m)">编辑</button>
                    <button
                      v-if="m.status === 'ENABLED'"
                      class="mp-link mn-danger"
                      :class="{ 'is-disabled': !can('disableMenu') }"
                      :title="reason('disableMenu')"
                      @click="askDisable(m)"
                    >停用</button>
                    <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableMenu') }" :title="reason('disableMenu')" @click="doEnable(m)">启用</button>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <p class="mp-note">
        说明：前端隐藏菜单/按钮只是体验层，后端接口仍会按权限码二次校验；菜单停用为逻辑操作，配置保留可随时恢复，全部变更写入审计日志。
      </p>
    </div>

    <!-- 新增 / 编辑菜单 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑菜单' : '新增菜单'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存菜单</AppButton>
      </template>
    </AppDrawer>

    <!-- 配置按钮权限点 -->
    <AppDrawer v-model:visible="btns.open" :title="'按钮权限点 · ' + btns.menuName">
      <div v-for="(b, i) in btns.list" :key="i" class="mn-btnrow">
        <input v-model="b.name" type="text" class="mn-input" placeholder="按钮名称，如 批量导出" />
        <input v-model="b.code" type="text" class="mn-input" placeholder="权限码，如 user:export" />
        <button class="mp-link mn-danger" @click="btns.list.splice(i, 1)">移除</button>
      </div>
      <button class="mp-link" @click="btns.list.push({ name: '', code: '' })">＋ 添加按钮权限点</button>
      <p class="mp-note" style="margin-top: var(--space-3)">权限码规范：模块:资源:动作（如 intern:weekly-report:review）；移除权限点不会删除历史授权记录。</p>
      <template #footer>
        <AppButton variant="ghost" @click="btns.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="btns.submitting" @click="submitButtons">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDisable"
      type="danger"
      :title="'停用菜单「' + (disableRow ? disableRow.name : '') + '」？'"
      message="停用后所有角色即时不可见该菜单（含子菜单与按钮）；配置保留，可随时恢复启用。"
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
 * 菜单权限管理（/admin/system/menus）：
 * 菜单树 / 新增编辑（系统管理员权限）/ 停用启用（留痕）/ 按钮权限点配置 / 按角色预览可见性。
 */
import { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemMenuView',
  components: {
    ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppConfirmDialog, FormFields
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      tree: [],
      previewRole: '',
      previewCodes: null,
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      btns: { open: false, menuId: '', menuName: '', list: [], submitting: false },
      confirmDisable: false,
      disableRow: null,
      disableSubmitting: false
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'createMenu', label: '＋ 新增菜单', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    previewRoleLabel() {
      const hit = this.ctx.filterOptions.roles.find((r) => r.value === this.previewRole)
      return hit ? hit.label : this.previewRole
    },
    formFields() {
      return [
        { key: 'name', label: '菜单名称', required: true },
        { key: 'code', label: '菜单编码', required: true, disabled: !!this.form.id, lockNote: this.form.id ? '（不可修改）' : '' },
        { key: 'path', label: '路由路径', placeholder: '/admin/...' },
        { key: 'sort', label: '排序号' },
        { key: 'reason', label: '变更原因', type: 'textarea', full: true, required: true, placeholder: '菜单结构变更需说明原因（写入审计），至少 5 个字' }
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
    dimmed(code) {
      return this.previewCodes !== null && !this.previewCodes.includes(code)
    },
    onToolbar(key) {
      if (key === 'createMenu') this.openEdit(null)
    },
    async loadPreview() {
      if (!this.previewRole) {
        this.previewCodes = null
        return
      }
      const res = await systemApi.previewRoleMenus(this.previewRole)
      if (res.code === 0) {
        const codes = res.data.menuCodes
        // 子菜单可见时父模块视为可见
        const parents = this.tree.filter((mod) => mod.children.some((m) => codes.includes(m.code))).map((mod) => mod.code)
        this.previewCodes = [...codes, ...parents]
      }
    },
    openEdit(row) {
      const key = row ? 'editMenu' : 'createMenu'
      if (!this.can(key)) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row ? { name: row.name, code: row.code, path: row.path, sort: String(row.sort ?? ''), reason: '' } : { name: '', code: '', path: '', sort: '', reason: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      if ((this.form.value.reason || '').trim().length < 5) errors.reason = '变更原因至少 5 个字'
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await systemApi.saveMenu({ id: this.form.id, ...this.form.value })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('菜单已保存，变更原因已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openButtons(menu) {
      if (!this.can('configMenuButtons')) return
      this.btns = { open: true, menuId: menu.id, menuName: menu.name, list: menu.buttons.map((b) => ({ ...b })), submitting: false }
    },
    async submitButtons() {
      const invalid = this.btns.list.some((b) => !b.name || !b.code)
      if (invalid) {
        toast.error('按钮名称与权限码均为必填')
        return
      }
      this.btns.submitting = true
      const res = await systemApi.saveMenu({ id: this.btns.menuId, name: this.btns.menuName, buttons: this.btns.list, reason: '配置按钮权限点' })
      this.btns.submitting = false
      if (res.code === 0) {
        // mock：直接同步到本地树
        this.tree.forEach((mod) => {
          const hit = mod.children.find((m) => m.id === this.btns.menuId)
          if (hit) hit.buttons = this.btns.list.map((b) => ({ ...b }))
        })
        toast.success('按钮权限点已保存并留痕')
        this.btns.open = false
      } else {
        toast.error(res.message)
      }
    },
    askDisable(row) {
      if (!this.can('disableMenu')) return
      this.disableRow = row
      this.confirmDisable = true
    },
    async doDisable({ reason }) {
      this.disableSubmitting = true
      const res = await systemApi.setMenuStatus(this.disableRow.id, { action: 'DISABLE', reason })
      this.disableSubmitting = false
      if (res.code === 0) {
        toast.success('菜单已停用（可恢复），原因已留痕')
        this.confirmDisable = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doEnable(row) {
      if (!this.can('disableMenu')) return
      const res = await systemApi.setMenuStatus(row.id, { action: 'ENABLE' })
      if (res.code === 0) {
        toast.success('菜单已恢复启用，已留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getMenuTree()
      if (res.code === 0) this.tree = res.data
      else this.error = res.message
      this.loading = false
      if (this.previewRole) this.loadPreview()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mn-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.mn-table th {
  text-align: left;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-base);
  white-space: nowrap;
}
.mn-table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}
.mn-mod td {
  background: var(--bg-subtle);
}
.mn-mod b {
  display: block;
}
.mn-sub {
  padding-left: var(--space-6);
  color: var(--text-primary);
}
.is-dim {
  opacity: 0.38;
}
.mn-btncode {
  display: inline-block;
  font-size: 10px;
  color: var(--primary-600);
  background: var(--primary-50);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-1);
  margin-right: var(--space-1);
}
.mn-danger {
  color: var(--danger-600);
}
.mn-preview {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.mn-select {
  height: 32px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  font: inherit;
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  background: var(--bg-card);
}
.mn-notice {
  font-size: var(--font-size-sm);
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.mn-btnrow {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  margin-bottom: var(--space-2);
}
.mn-input {
  flex: 1;
  height: 32px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  font: inherit;
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
