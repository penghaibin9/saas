<template>
  <AppCard class="wf-role-panel">
    <div v-if="!role" class="wf-role-panel__empty">从左侧选择一个角色查看权限详情</div>
    <template v-else>
      <div class="wf-role-panel__head">
        <div>
          <h3 class="wf-role-panel__title">{{ role.roleName }}</h3>
          <code class="wf-role-panel__code">{{ role.roleCode }}</code>
        </div>
        <DataScopeTag :scope="editing ? draftScope : role.dataScope" />
      </div>
      <p class="wf-role-panel__desc">{{ role.description }}</p>
      <div class="wf-role-panel__stats">
        <span>绑定用户 {{ role.userCount }} 人</span>
        <span>权限 {{ (editing ? draftKeys : role.permissionKeys).length }} 项</span>
      </div>

      <div v-if="editing" class="wf-role-panel__scope-edit">
        <label class="wf-role-panel__label">数据范围</label>
        <select v-model="draftScope" class="wf-role-panel__select">
          <option v-for="(label, code) in scopeOptions" :key="code" :value="code">{{ label }}</option>
        </select>
      </div>

      <div class="wf-role-panel__perms">
        <h4 class="wf-role-panel__sub">权限点</h4>
        <div v-if="editing" class="wf-role-panel__perm-edit">
          <label v-for="p in allPermissions" :key="p.permissionKey" class="wf-role-panel__perm-item">
            <input type="checkbox" :value="p.permissionKey" v-model="draftKeys" />
            <PermissionTag :permission-key="p.permissionKey" :type="p.type" />
          </label>
        </div>
        <div v-else class="wf-role-panel__perm-view">
          <PermissionTag
            v-for="key in role.permissionKeys"
            :key="key"
            :permission-key="key"
            :type="typeOf(key)"
          />
          <span v-if="!role.permissionKeys.length" class="wf-role-panel__none">暂无权限点</span>
        </div>
      </div>

      <div class="wf-role-panel__actions">
        <template v-if="editing">
          <AppButton variant="secondary" @click="cancelEdit">取消</AppButton>
          <AppButton variant="primary" :loading="submitting" :disabled="readonly" @click="save">保存</AppButton>
        </template>
        <AppButton v-else variant="secondary" :disabled="readonly || !canEdit" @click="startEdit">
          编辑权限
        </AppButton>
      </div>
    </template>
  </AppCard>
</template>

<script>
/** RolePermissionPanel —— 角色权限详情与 mock 编辑（勾选权限点 + 调整数据范围） */
import { AppCard, AppButton } from '@/components/ui'
import PermissionTag from './PermissionTag.vue'
import DataScopeTag from './DataScopeTag.vue'
import { DATA_SCOPE_LABELS } from '../constants/workflow.constants'

export default {
  name: 'RolePermissionPanel',
  components: { AppCard, AppButton, PermissionTag, DataScopeTag },
  props: {
    role: { type: Object, default: null },
    allPermissions: { type: Array, default: () => [] },
    readonly: { type: Boolean, default: false },
    canEdit: { type: Boolean, default: true },
    submitting: { type: Boolean, default: false }
  },
  emits: ['save'],
  data() {
    return { editing: false, draftKeys: [], draftScope: '' }
  },
  computed: {
    scopeOptions() {
      return DATA_SCOPE_LABELS
    }
  },
  watch: {
    role() {
      this.cancelEdit()
    }
  },
  methods: {
    typeOf(key) {
      return this.allPermissions.find((p) => p.permissionKey === key)?.type || 'BUTTON'
    },
    startEdit() {
      this.draftKeys = [...(this.role?.permissionKeys || [])]
      this.draftScope = this.role?.dataScope || 'SELF'
      this.editing = true
    },
    cancelEdit() {
      this.editing = false
      this.draftKeys = []
      this.draftScope = ''
    },
    save() {
      this.$emit('save', {
        roleId: this.role.roleId,
        permissionKeys: [...this.draftKeys],
        dataScope: this.draftScope
      })
      this.editing = false
    }
  }
}
</script>

<style scoped>
.wf-role-panel { padding: var(--card-padding-pc); display: flex; flex-direction: column; gap: var(--space-3); }
.wf-role-panel__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; padding: var(--space-10) 0; }
.wf-role-panel__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.wf-role-panel__title { margin: 0; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.wf-role-panel__code { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wf-role-panel__desc { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
.wf-role-panel__stats { display: flex; gap: var(--space-4); font-size: var(--font-size-sm); color: var(--text-secondary); }
.wf-role-panel__label { font-size: var(--font-size-sm); color: var(--text-primary); margin-right: var(--space-2); }
.wf-role-panel__select {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-1) var(--space-2);
  font: inherit;
  color: var(--text-primary);
  background: var(--bg-card);
}
.wf-role-panel__sub { margin: 0 0 var(--space-2); font-size: var(--font-size-base); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.wf-role-panel__perm-view { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.wf-role-panel__perm-edit { display: flex; flex-direction: column; gap: var(--space-2); max-height: 320px; overflow: auto; }
.wf-role-panel__perm-item { display: flex; align-items: center; gap: var(--space-2); cursor: pointer; }
.wf-role-panel__none { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.wf-role-panel__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
</style>
