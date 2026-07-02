<template>
  <span class="stu-scope-hint">数据范围：{{ hint.label }}</span>
</template>

<script>
/** StudentDataScopeHint — 当前角色数据范围提示（复用 workflow permissionContext） */
import { getStudentDataScopeHint } from '../helpers/student-security.helper'

export default {
  name: 'StudentDataScopeHint',
  computed: {
    hint() {
      return getStudentDataScopeHint()
    }
  }
}
</script>

<style scoped>
.stu-scope-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--info-50);
  border: 1px solid var(--info-100);
  font-size: var(--font-size-xs);
  color: var(--info-700);
  white-space: nowrap;
}
</style>
