<template>
  <div class="bab">
    <AppButton
      v-for="a in visibleActions"
      :key="a.key"
      variant="ghost"
      :disabled="a.disabled"
      :title="a.disabled ? a.disabledReason || '当前角色无此操作权限' : ''"
      @click="$emit('action', a.key)"
    >
      {{ a.label }}
    </AppButton>
  </div>
</template>

<script>
/**
 * BatchActionBar — 批量操作按钮组（渲染在 DataTable 的 #batch-actions 插槽内）。
 * actions 由 mock/api 的 batchActions 下发并按 permissionActions 预处理。
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'BatchActionBar',
  components: { AppButton },
  props: {
    actions: { type: Array, default: () => [] }
  },
  emits: ['action'],
  computed: {
    visibleActions() {
      return this.actions.filter((a) => a.visible !== false)
    }
  }
}
</script>

<style scoped>
.bab {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}
</style>
