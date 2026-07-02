<template>
  <span class="wf-perm-tag" :class="`is-${type.toLowerCase()}`" :title="permissionKey">
    <code class="wf-perm-tag__key">{{ permissionKey }}</code>
    <span class="wf-perm-tag__type">{{ typeLabel }}</span>
  </span>
</template>

<script>
/** PermissionTag —— 权限点标签（module.resource.action + 类型角标） */
import { PERMISSION_TYPE_LABELS } from '../constants/workflow.constants'

export default {
  name: 'PermissionTag',
  props: {
    permissionKey: { type: String, required: true },
    type: { type: String, default: 'BUTTON' }
  },
  computed: {
    typeLabel() {
      return PERMISSION_TYPE_LABELS[this.type] || this.type
    }
  }
}
</script>

<style scoped>
.wf-perm-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  font-size: var(--font-size-xs);
}
.wf-perm-tag__key {
  font-family: var(--font-family-base);
  color: var(--text-secondary);
}
.wf-perm-tag__type {
  color: var(--text-tertiary);
  border-left: 1px solid var(--border-base);
  padding-left: var(--space-2);
  white-space: nowrap;
}
.is-menu .wf-perm-tag__type { color: var(--primary-600); }
.is-page .wf-perm-tag__type { color: var(--info-600); }
.is-data .wf-perm-tag__type { color: var(--warning-600); }
</style>
